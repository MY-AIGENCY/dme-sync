import boto3
import os
from datetime import timezone

BUCKET = os.getenv("S3_BUCKET_NAME", "raw-site-data")
PREFIX = ""  # Set to a subfolder if needed
MAX_FILES = 10  # Limit for display

s3 = boto3.client("s3")

print(f"Listing objects in bucket: {BUCKET}")
response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)

if "Contents" not in response:
    print("No objects found in bucket.")
    exit(0)

objects = response["Contents"]
print(f"Found {len(objects)} objects. Showing up to {MAX_FILES}:")
for obj in objects[:MAX_FILES]:
    print(f"- {obj['Key']} (LastModified: {obj['LastModified'].astimezone(timezone.utc)})")

# Optionally, inspect the first file
if objects:
    key = objects[0]["Key"]
    print(f"\nInspecting first file: {key}")
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    content = obj["Body"].read().decode("utf-8", errors="replace")
    print("First 20 lines:")
    for line in content.splitlines()[:20]:
        print(line) 