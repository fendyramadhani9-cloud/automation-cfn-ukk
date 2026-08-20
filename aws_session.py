"""
AWS Session management and STS validation.
Supports temporary credentials (Access Key, Secret Key, Session Token) for AWS Academy Learner Lab.
"""
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import DEFAULT_REGION


class AWSSessionManager:
    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        region_name: str = DEFAULT_REGION,
    ):
        self.aws_access_key_id = aws_access_key_id.strip() if aws_access_key_id else None
        self.aws_secret_access_key = aws_secret_access_key.strip() if aws_secret_access_key else None
        self.aws_session_token = aws_session_token.strip() if aws_session_token else None
        self.profile_name = profile_name
        self.region_name = region_name
        self.session = None
        self.account_id = None
        self.arn = None
        self.user_id = None

    def initialize(self) -> Dict[str, Any]:
        """Create boto3 session and validate STS caller identity."""
        try:
            # 1. Direct credentials from participant (AWS Academy Learner Lab)
            if self.aws_access_key_id and self.aws_secret_access_key:
                self.session = boto3.Session(
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    aws_session_token=self.aws_session_token,
                    region_name=self.region_name,
                )
            # 2. Local profile if specified
            elif self.profile_name:
                self.session = boto3.Session(profile_name=self.profile_name, region_name=self.region_name)
            # 3. Default environment credentials
            else:
                self.session = boto3.Session(region_name=self.region_name)

            sts = self.session.client("sts")
            identity = sts.get_caller_identity()
            self.account_id = identity.get("Account")
            self.arn = identity.get("Arn")
            self.user_id = identity.get("UserId")

            return {
                "success": True,
                "account_id": self.account_id,
                "arn": self.arn,
                "user_id": self.user_id,
                "region": self.region_name,
            }
        except NoCredentialsError:
            return {
                "success": False,
                "error": "No AWS credentials found for this participant.",
            }
        except ClientError as e:
            return {
                "success": False,
                "error": f"STS Authentication Error (Credential expired or invalid): {e}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during AWS session setup: {str(e)}",
            }

    def get_client(self, service_name: str):
        """Retrieve a boto3 client with the active session."""
        if not self.session:
            raise RuntimeError("AWS session is not initialized.")
        return self.session.client(service_name, region_name=self.region_name)

    def get_resource(self, service_name: str):
        """Retrieve a boto3 resource with the active session."""
        if not self.session:
            raise RuntimeError("AWS session is not initialized.")
        return self.session.resource(service_name, region_name=self.region_name)
