#!/usr/bin/env python3

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def aws_quote(value, safe="-_.~"):
    return urllib.parse.quote(str(value), safe=safe)


def sign(key, message):
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def signing_key(secret_access_key, date_stamp, region, service):
    date_key = sign(("AWS4" + secret_access_key).encode("utf-8"), date_stamp)
    region_key = sign(date_key, region)
    service_key = sign(region_key, service)
    return sign(service_key, "aws4_request")


def canonical_query(params):
    pairs = []
    for key, value in params.items():
        if value is None:
            continue
        pairs.append((aws_quote(key), aws_quote(value)))
    return "&".join(f"{key}={value}" for key, value in sorted(pairs))


def signed_list_url(endpoint, bucket, region, access_key_id, secret_access_key, prefix, token):
    now = dt.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    service = "s3"
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.netloc
    canonical_uri = f"/{aws_quote(bucket, safe='-_.~/')}"
    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    params = {
        "list-type": "2",
        "prefix": prefix,
    }
    if token:
        params["continuation-token"] = token

    canonical_headers = (
        f"host:{host}\n"
        "x-amz-content-sha256:UNSIGNED-PAYLOAD\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join([
        "GET",
        canonical_uri,
        canonical_query(params),
        canonical_headers,
        signed_headers,
        "UNSIGNED-PAYLOAD",
    ])
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(
        signing_key(secret_access_key, date_stamp, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    query = canonical_query(params)
    url = f"{endpoint.rstrip('/')}{canonical_uri}?{query}"
    headers = {
        "Authorization": authorization,
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
        "x-amz-date": amz_date,
    }
    return url, headers


def list_objects(endpoint, bucket, region, access_key_id, secret_access_key, prefix):
    token = None
    while True:
        url, headers = signed_list_url(
            endpoint,
            bucket,
            region,
            access_key_id,
            secret_access_key,
            prefix,
            token,
        )
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request) as response:
            xml_body = response.read()

        root = ET.fromstring(xml_body)
        namespace = ""
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0] + "}"

        for contents in root.findall(f"{namespace}Contents"):
            key = contents.findtext(f"{namespace}Key")
            size = int(contents.findtext(f"{namespace}Size") or 0)
            if key:
                yield {"key": key, "size": size}

        is_truncated = (root.findtext(f"{namespace}IsTruncated") or "").lower() == "true"
        token = root.findtext(f"{namespace}NextContinuationToken")
        if not is_truncated or not token:
            break


def paper_ids_for_key(key):
    ids = []
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", key)
    if match:
        base_id = match.group(1)
        ids.append(base_id)
        full_match = re.search(r"(\d{4}\.\d{4,5}v\d+)", key)
        if full_match:
            ids.append(full_match.group(1))

    parts = Path(key).parts
    if len(parts) >= 2:
        ids.append(parts[-2])

    return list(dict.fromkeys(ids))


def image_label(key):
    return Path(key).name


def sort_key(item):
    filename = Path(item["key"]).name
    match = re.match(r"(x|img-)(\d+)(\.[^.]+)$", filename, re.I)
    if match:
        return (0, match.group(1).lower(), int(match.group(2)), filename.lower())
    return (1, filename.lower())


def public_url_for_key(public_base_url, key):
    clean_key = key.lstrip("/")
    return f"{public_base_url.rstrip('/')}/{aws_quote(clean_key, safe='-_.~/')}"


def prefixes_for_paper_id(paper_id):
    return [
        f"figures/{paper_id}/",
        f"figures-normalized/figures/{paper_id}/",
    ]


def get_prefixes(args):
    prefixes = []
    prefixes.extend(args.prefix)
    for paper_id in args.paper_id:
        prefixes.extend(prefixes_for_paper_id(paper_id))

    prefixes = list(dict.fromkeys(prefixes))
    if not prefixes:
        raise SystemExit(
            "Refusing to list the whole bucket. Pass --paper-id <id> or --prefix <bucket-prefix>."
        )
    return prefixes


def build_manifest(args):
    endpoint = args.endpoint or f"https://{args.account_id}.r2.cloudflarestorage.com"
    manifest = {}

    for prefix in get_prefixes(args):
        print(f"Listing prefix: {prefix}")
        objects = list_objects(
            endpoint,
            args.bucket,
            args.region,
            args.access_key_id,
            args.secret_access_key,
            prefix,
        )
        for obj in objects:
            key = obj["key"]
            if Path(key).suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            ids = paper_ids_for_key(key)
            if not ids:
                continue

            item = {
                "key": key,
                "label": image_label(key),
                "url": public_url_for_key(args.public_base_url, key),
                "size": obj["size"],
            }
            for paper_id in ids:
                manifest.setdefault(paper_id, []).append(item)

    for images in manifest.values():
        images.sort(key=sort_key)

    output_path = Path(args.out)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {sum(len(images) for images in manifest.values())} image entries to {output_path}")


def env_or_error(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def parse_args():
    parser = argparse.ArgumentParser(description="Build figure_manifest.json by listing a Cloudflare R2/S3 bucket and mapping keys to public image URLs.")
    parser.add_argument("--account-id", default=os.environ.get("ALPHAXIV_R2_ACCOUNT_ID", ""))
    parser.add_argument("--endpoint", "--endpoint-url", dest="endpoint", default=os.environ.get("ALPHAXIV_R2_ENDPOINT", ""))
    parser.add_argument("--bucket", default=os.environ.get("ALPHAXIV_R2_BUCKET", ""))
    parser.add_argument("--region", default=os.environ.get("ALPHAXIV_AWS_DEFAULT_REGION", "auto"))
    parser.add_argument("--access-key-id", default=os.environ.get("ALPHAXIV_AWS_ACCESS_KEY_ID", ""))
    parser.add_argument("--secret-access-key", default=os.environ.get("ALPHAXIV_AWS_SECRET_ACCESS_KEY", ""))
    parser.add_argument("--paper-id", action="append", default=[], help="Paper id/folder to list, e.g. 2504.04635 or 2504.04635v1. May be repeated.")
    parser.add_argument("--prefix", action="append", default=[], help="Exact bucket prefix to list. May be repeated.")
    parser.add_argument("--public-base-url", default="https://paper-assets.alphaxiv.org")
    parser.add_argument("--out", default=str(ROOT / "figure_manifest.json"))
    args = parser.parse_args()

    if not args.endpoint and not args.account_id:
        args.account_id = env_or_error("ALPHAXIV_R2_ACCOUNT_ID")
    if not args.bucket:
        args.bucket = env_or_error("ALPHAXIV_R2_BUCKET")
    if not args.access_key_id:
        args.access_key_id = env_or_error("ALPHAXIV_AWS_ACCESS_KEY_ID")
    if not args.secret_access_key:
        args.secret_access_key = env_or_error("ALPHAXIV_AWS_SECRET_ACCESS_KEY")
    return args


if __name__ == "__main__":
    try:
        build_manifest(parse_args())
    except urllib.error.HTTPError as error:
        sys.stderr.write(error.read().decode("utf-8", errors="replace"))
        raise
