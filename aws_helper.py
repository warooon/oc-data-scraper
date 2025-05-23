import boto3
from io import BytesIO

S3_BUCKET = 'genai-poc-s3-bucket'
AWS_REGION = 'us-east-2'

s3_client = boto3.client('s3', region_name=AWS_REGION)

def upload_to_s3(file_obj_or_path, filename):
    if isinstance(file_obj_or_path, BytesIO):
        s3_client.upload_fileobj(file_obj_or_path, S3_BUCKET, filename)
    else:
        with open(file_obj_or_path, "rb") as f:
            s3_client.upload_fileobj(f, S3_BUCKET, filename)

    s3_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
    return s3_url