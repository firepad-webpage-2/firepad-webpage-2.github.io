from datasets import load_dataset
import pandas as pd

# Replace 'dataset_name' with the name of the dataset you want to use
# For example, 'imdb', 'squad', etc.
dataset_name = 'ccdv/arxiv-summarization'  # e.g., 'imdb'

# Optionally, specify the split you want to use (e.g., 'train', 'test')
split_name = 'train'  # Change as needed

# Load the dataset
dataset = load_dataset(dataset_name, split=split_name)

# Select the first 100 entries
first_100 = dataset.select(range(100))

# Convert to a pandas DataFrame
df = first_100.to_pandas()

# Save the DataFrame to a CSV file
output_filename = 'dataset100.csv'
df.to_csv(output_filename, index=False)

print(f"First 100 entries have been saved to {output_filename}")
