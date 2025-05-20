import boto3
import os
import json

BUCKET = os.getenv("S3_BUCKET_NAME", "raw-site-data")
s3 = boto3.client("s3")

def list_keys_with_govuk():
    keys_to_delete = []
    continuation_token = None
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=BUCKET, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=BUCKET)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if "gov.uk" in key:
                keys_to_delete.append(key)
            elif key.endswith(".json") or key.endswith(".jsonl"):
                # Check content for gov.uk
                try:
                    body = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode("utf-8", errors="replace")
                    if "gov.uk" in body:
                        keys_to_delete.append(key)
                except Exception as e:
                    print(f"Error reading {key}: {e}")
        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break
    return keys_to_delete

def delete_keys(keys):
    for key in keys:
        print(f"Deleting: {key}")
        s3.delete_object(Bucket=BUCKET, Key=key)
    print(f"Deleted {len(keys)} objects.")

def reset_run_history():
    log_key = 'run_history.jsonl'
    try:
        resp = s3.get_object(Bucket=BUCKET, Key=log_key)
        lines = resp['Body'].read().decode().splitlines()
        new_lines = [line for line in lines if "gov.uk" not in line]
        s3.put_object(Bucket=BUCKET, Key=log_key, Body='\n'.join(new_lines).encode('utf-8'))
        print(f"Reset {log_key}, removed {len(lines) - len(new_lines)} lines.")
    except s3.exceptions.NoSuchKey:
        print(f"No {log_key} found to reset.")

govuk_keys = list_keys_with_govuk()
delete_keys(govuk_keys)
reset_run_history() 