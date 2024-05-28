import json
import os

from elasticsearch import Elasticsearch, helpers

# Initialize Elasticsearch client
api_key = os.environ.get("ELASTIC_API_KEY")
hosts = os.environ.get("ELASTIC_HOSTS")
client = Elasticsearch(hosts=hosts.split(","), api_key=api_key)


# Function to process and upload data to Elasticsearch
def process_and_upload_to_elasticsearch(file_path, batch_size=10000):
    actions = []
    line_count = 0

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            # Split the line by tab character
            parts = line.strip().split("\t")

            if len(parts) > 0:
                try:
                    # Parse the JSON part
                    json_data = json.loads(parts[0])

                    # Create an action for the bulk API
                    actions.append(json_data)

                    # Increment the line count
                    line_count += 1

                    # If batch_size is reached, upload to Elasticsearch
                    if line_count % batch_size == 0:
                        helpers.bulk(client, actions, index="search-keeptest")
                        print(f"Uploaded {line_count} lines to Elasticsearch")
                        actions = []  # Reset actions list

                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing line: {e}")
                    continue

        # Upload any remaining actions to Elasticsearch
        if actions:
            helpers.bulk(client, actions, index="search-keeptest")
            print(
                f"Uploaded the remaining {line_count % batch_size} lines to Elasticsearch"
            )


# Call the function with the appropriate file path and index name
process_and_upload_to_elasticsearch("/Users/shaharglazner/output.json")
