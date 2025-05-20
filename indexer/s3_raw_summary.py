import boto3
import os
from datetime import timezone

BUCKET = os.getenv("S3_BUCKET_NAME", "raw-site-data")
PREFIX = "raw/"

s3 = boto3.client("s3")

print(f"Listing objects in bucket: {BUCKET} with prefix: {PREFIX}")
objects = []
continuation_token = None
while True:
    if continuation_token:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX, ContinuationToken=continuation_token)
    else:
        response = s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
    if "Contents" in response:
        objects.extend(response["Contents"])
    if response.get("IsTruncated"):
        continuation_token = response["NextContinuationToken"]
    else:
        break

if not objects:
    print("No raw objects found.")
    exit(0)

# Sort by LastModified
objects.sort(key=lambda x: x["LastModified"])

total_size = sum(obj["Size"] for obj in objects)
print(f"Found {len(objects)} raw objects. Total size: {total_size/1024/1024:.2f} MB")

first = objects[0]
last = objects[-1]
print(f"First raw doc: {first['Key']} (LastModified: {first['LastModified'].astimezone(timezone.utc)}, Size: {first['Size']} bytes)")
print(f"Last raw doc: {last['Key']} (LastModified: {last['LastModified'].astimezone(timezone.utc)}, Size: {last['Size']} bytes)") 