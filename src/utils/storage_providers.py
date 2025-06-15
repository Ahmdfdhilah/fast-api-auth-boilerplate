"""Storage provider implementations."""

import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
import aiofiles

from src.utils.storage import StorageInterface, FileInfo
from src.core.config import settings


class LocalStorageProvider(StorageInterface):
    """Local file system storage provider."""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.UPLOADS_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.base_url = f"/{settings.STATIC_FILES_PATH}"
    
    async def upload_file(
        self, 
        file_data: bytes, 
        filename: str, 
        content_type: str,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileInfo:
        """Upload file to local storage."""
        unique_filename = self.generate_unique_filename(filename, folder)
        file_path = self.base_path / unique_filename
        
        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_data)
        
        # Generate URL
        url = f"{self.base_url}/{unique_filename}".replace("\\", "/")
        
        return FileInfo(
            filename=filename,
            content_type=content_type,
            size=len(file_data),
            url=url,
            key=unique_filename,
            metadata=metadata
        )
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from local storage."""
        try:
            file_path = self.base_path / key
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    async def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get file URL (local storage doesn't support expiring URLs)."""
        return f"{self.base_url}/{key}".replace("\\", "/")
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in local storage."""
        file_path = self.base_path / key
        return file_path.exists()
    
    async def list_files(self, folder: str = "", limit: int = 100) -> List[FileInfo]:
        """List files in local storage folder."""
        folder_path = self.base_path / folder if folder else self.base_path
        
        if not folder_path.exists():
            return []
        
        files = []
        for file_path in folder_path.iterdir():
            if file_path.is_file() and len(files) < limit:
                relative_path = file_path.relative_to(self.base_path)
                stat = file_path.stat()
                
                files.append(FileInfo(
                    filename=file_path.name,
                    content_type=self.get_content_type(file_path.name),
                    size=stat.st_size,
                    url=f"{self.base_url}/{relative_path}".replace("\\", "/"),
                    key=str(relative_path).replace("\\", "/")
                ))
        
        return files


class AWSS3StorageProvider(StorageInterface):
    """AWS S3 storage provider."""
    
    def __init__(self):
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket_name = settings.AWS_S3_BUCKET
            self.ClientError = ClientError
            self.NoCredentialsError = NoCredentialsError
            
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="boto3 library not installed. Install with: pip install boto3"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize AWS S3 client: {str(e)}"
            )
    
    async def upload_file(
        self, 
        file_data: bytes, 
        filename: str, 
        content_type: str,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileInfo:
        """Upload file to AWS S3."""
        try:
            unique_filename = self.generate_unique_filename(filename, folder)
            
            extra_args = {
                'ContentType': content_type,
                'Metadata': metadata or {}
            }
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=unique_filename,
                Body=file_data,
                **extra_args
            )
            
            url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{unique_filename}"
            
            return FileInfo(
                filename=filename,
                content_type=content_type,
                size=len(file_data),
                url=url,
                key=unique_filename,
                metadata=metadata
            )
            
        except self.ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to S3: {str(e)}"
            )
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from AWS S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except self.ClientError:
            return False
    
    async def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get signed URL for AWS S3 file."""
        try:
            if expires_in:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expires_in
                )
                return url
            else:
                return f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"
        except self.ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get S3 URL: {str(e)}"
            )
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in AWS S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except self.ClientError:
            return False
    
    async def list_files(self, folder: str = "", limit: int = 100) -> List[FileInfo]:
        """List files in AWS S3 bucket/folder."""
        try:
            prefix = f"{folder}/" if folder else ""
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=limit
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append(FileInfo(
                    filename=obj['Key'].split('/')[-1],
                    content_type=self.get_content_type(obj['Key']),
                    size=obj['Size'],
                    url=f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{obj['Key']}",
                    key=obj['Key']
                ))
            
            return files
            
        except self.ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list S3 files: {str(e)}"
            )


class GCPStorageProvider(StorageInterface):
    """Google Cloud Storage provider."""
    
    def __init__(self):
        try:
            from google.cloud import storage
            from google.cloud.exceptions import GoogleCloudError
            
            if settings.GCP_SERVICE_ACCOUNT_KEY_PATH:
                self.client = storage.Client.from_service_account_json(
                    settings.GCP_SERVICE_ACCOUNT_KEY_PATH
                )
            else:
                self.client = storage.Client(project=settings.GCP_PROJECT_ID)
            
            self.bucket = self.client.bucket(settings.GCP_STORAGE_BUCKET)
            self.GoogleCloudError = GoogleCloudError
            
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="google-cloud-storage library not installed. Install with: pip install google-cloud-storage"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize GCP Storage client: {str(e)}"
            )
    
    async def upload_file(
        self, 
        file_data: bytes, 
        filename: str, 
        content_type: str,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileInfo:
        """Upload file to Google Cloud Storage."""
        try:
            unique_filename = self.generate_unique_filename(filename, folder)
            blob = self.bucket.blob(unique_filename)
            
            blob.upload_from_string(
                file_data,
                content_type=content_type
            )
            
            if metadata:
                blob.metadata = metadata
                blob.patch()
            
            url = f"https://storage.googleapis.com/{settings.GCP_STORAGE_BUCKET}/{unique_filename}"
            
            return FileInfo(
                filename=filename,
                content_type=content_type,
                size=len(file_data),
                url=url,
                key=unique_filename,
                metadata=metadata
            )
            
        except self.GoogleCloudError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to GCP Storage: {str(e)}"
            )
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from Google Cloud Storage."""
        try:
            blob = self.bucket.blob(key)
            blob.delete()
            return True
        except self.GoogleCloudError:
            return False
    
    async def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get signed URL for GCP Storage file."""
        try:
            blob = self.bucket.blob(key)
            if expires_in:
                from datetime import timedelta
                url = blob.generate_signed_url(
                    expiration=timedelta(seconds=expires_in),
                    method='GET'
                )
                return url
            else:
                return f"https://storage.googleapis.com/{settings.GCP_STORAGE_BUCKET}/{key}"
        except self.GoogleCloudError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get GCP Storage URL: {str(e)}"
            )
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in Google Cloud Storage."""
        try:
            blob = self.bucket.blob(key)
            return blob.exists()
        except self.GoogleCloudError:
            return False
    
    async def list_files(self, folder: str = "", limit: int = 100) -> List[FileInfo]:
        """List files in GCP Storage bucket/folder."""
        try:
            prefix = f"{folder}/" if folder else None
            blobs = self.client.list_blobs(
                self.bucket,
                prefix=prefix,
                max_results=limit
            )
            
            files = []
            for blob in blobs:
                files.append(FileInfo(
                    filename=blob.name.split('/')[-1],
                    content_type=blob.content_type or self.get_content_type(blob.name),
                    size=blob.size,
                    url=f"https://storage.googleapis.com/{settings.GCP_STORAGE_BUCKET}/{blob.name}",
                    key=blob.name
                ))
            
            return files
            
        except self.GoogleCloudError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list GCP Storage files: {str(e)}"
            )


class AzureBlobStorageProvider(StorageInterface):
    """Azure Blob Storage provider."""
    
    def __init__(self):
        try:
            from azure.storage.blob import BlobServiceClient
            from azure.core.exceptions import AzureError
            
            self.blob_service = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
            self.container_name = settings.AZURE_STORAGE_CONTAINER
            self.AzureError = AzureError
            
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="azure-storage-blob library not installed. Install with: pip install azure-storage-blob"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize Azure Blob Storage client: {str(e)}"
            )
    
    async def upload_file(
        self, 
        file_data: bytes, 
        filename: str, 
        content_type: str,
        folder: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> FileInfo:
        """Upload file to Azure Blob Storage."""
        try:
            unique_filename = self.generate_unique_filename(filename, folder)
            blob_client = self.blob_service.get_blob_client(
                container=self.container_name,
                blob=unique_filename
            )
            
            blob_client.upload_blob(
                file_data,
                content_type=content_type,
                metadata=metadata,
                overwrite=True
            )
            
            # Extract account name from connection string for URL
            account_name = settings.AZURE_STORAGE_CONNECTION_STRING.split("AccountName=")[1].split(";")[0]
            url = f"https://{account_name}.blob.core.windows.net/{self.container_name}/{unique_filename}"
            
            return FileInfo(
                filename=filename,
                content_type=content_type,
                size=len(file_data),
                url=url,
                key=unique_filename,
                metadata=metadata
            )
            
        except self.AzureError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to Azure Blob Storage: {str(e)}"
            )
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from Azure Blob Storage."""
        try:
            blob_client = self.blob_service.get_blob_client(
                container=self.container_name,
                blob=key
            )
            blob_client.delete_blob()
            return True
        except self.AzureError:
            return False
    
    async def get_file_url(self, key: str, expires_in: Optional[int] = None) -> str:
        """Get signed URL for Azure Blob Storage file."""
        try:
            blob_client = self.blob_service.get_blob_client(
                container=self.container_name,
                blob=key
            )
            
            if expires_in:
                from datetime import datetime, timedelta
                from azure.storage.blob import generate_blob_sas, BlobSasPermissions
                
                sas_token = generate_blob_sas(
                    account_name=blob_client.account_name,
                    container_name=self.container_name,
                    blob_name=key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(seconds=expires_in)
                )
                return f"{blob_client.url}?{sas_token}"
            else:
                return blob_client.url
                
        except self.AzureError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get Azure Blob Storage URL: {str(e)}"
            )
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in Azure Blob Storage."""
        try:
            blob_client = self.blob_service.get_blob_client(
                container=self.container_name,
                blob=key
            )
            return blob_client.exists()
        except self.AzureError:
            return False
    
    async def list_files(self, folder: str = "", limit: int = 100) -> List[FileInfo]:
        """List files in Azure Blob Storage container/folder."""
        try:
            container_client = self.blob_service.get_container_client(self.container_name)
            name_starts_with = f"{folder}/" if folder else None
            
            blobs = container_client.list_blobs(
                name_starts_with=name_starts_with,
                max_results=limit
            )
            
            files = []
            account_name = settings.AZURE_STORAGE_CONNECTION_STRING.split("AccountName=")[1].split(";")[0]
            
            for blob in blobs:
                files.append(FileInfo(
                    filename=blob.name.split('/')[-1],
                    content_type=blob.content_settings.content_type or self.get_content_type(blob.name),
                    size=blob.size,
                    url=f"https://{account_name}.blob.core.windows.net/{self.container_name}/{blob.name}",
                    key=blob.name
                ))
            
            return files
            
        except self.AzureError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to list Azure Blob Storage files: {str(e)}"
            )