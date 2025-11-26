"""Utility for deploying the broker to Lambda behind API Gateway.

This script packages the broker code, creates or updates the Lambda function,
creates an HTTP API Gateway route at ``POST /ingest/audio``, and prints the
invoke URL. It intentionally avoids CloudFormation so you can run it from a
minimal environment with only AWS credentials configured.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

import boto3
from botocore.exceptions import ClientError


BROKER_FILES = [
    Path("broker/__init__.py"),
    Path("broker/handler.py"),
]


@dataclass
class DeployConfig:
    function_name: str
    role_arn: str
    api_name: str
    stage_name: str
    timeout: int = 15
    memory_size: int = 256
    region: Optional[str] = None


def _zip_broker_code(root: Path) -> bytes:
    """Return a zipfile payload containing the broker package."""

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "broker.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src in BROKER_FILES:
                full_path = root / src
                if not full_path.exists():
                    raise FileNotFoundError(f"Expected file missing: {full_path}")
                zf.write(full_path, arcname=str(src))
        return zip_path.read_bytes()


def _ensure_lambda_function(
    lambda_client,
    cfg: DeployConfig,
    zip_bytes: bytes,
) -> Dict:
    """Create or update the Lambda function and return its description."""

    try:
        lambda_client.get_function(FunctionName=cfg.function_name)
        exists = True
    except lambda_client.exceptions.ResourceNotFoundException:
        exists = False

    kwargs = {
        "FunctionName": cfg.function_name,
        "Runtime": "python3.11",
        "Role": cfg.role_arn,
        "Handler": "broker.handler.lambda_handler",
        "Timeout": cfg.timeout,
        "MemorySize": cfg.memory_size,
        "Architectures": ["arm64"],
        "Environment": {"Variables": {}},
    }

    if exists:
        lambda_client.update_function_code(FunctionName=cfg.function_name, ZipFile=zip_bytes)
        lambda_client.update_function_configuration(**kwargs)
    else:
        kwargs["Code"] = {"ZipFile": zip_bytes}
        lambda_client.create_function(**kwargs)

    return lambda_client.get_function(FunctionName=cfg.function_name)


def _find_api_by_name(apigw_client, name: str) -> Optional[Dict]:
    paginator = apigw_client.get_paginator("get_apis")
    for page in paginator.paginate():
        for api in page.get("Items", []):
            if api.get("Name") == name:
                return api
    return None


def _ensure_integration(apigw_client, api_id: str, lambda_arn: str) -> str:
    integrations = apigw_client.get_integrations(ApiId=api_id).get("Items", [])
    for integration in integrations:
        if integration.get("IntegrationUri") == lambda_arn:
            return integration["IntegrationId"]

    response = apigw_client.create_integration(
        ApiId=api_id,
        IntegrationType="AWS_PROXY",
        IntegrationUri=lambda_arn,
        PayloadFormatVersion="2.0",
        TimeoutInMillis=15000,
    )
    return response["IntegrationId"]


def _ensure_route(apigw_client, api_id: str, integration_id: str) -> None:
    route_key = "POST /ingest/audio"
    routes = apigw_client.get_routes(ApiId=api_id).get("Items", [])
    for route in routes:
        if route.get("RouteKey") == route_key:
            return

    apigw_client.create_route(
        ApiId=api_id,
        RouteKey=route_key,
        Target=f"integrations/{integration_id}",
    )


def _ensure_stage(apigw_client, api_id: str, stage_name: str) -> None:
    stages = apigw_client.get_stages(ApiId=api_id).get("Items", [])
    for stage in stages:
        if stage.get("StageName") == stage_name:
            return
    apigw_client.create_stage(ApiId=api_id, StageName=stage_name, AutoDeploy=True)


def _allow_apigw_invoke(lambda_client, function_name: str, api_id: str, region: str, account_id: str) -> None:
    statement_id = f"apigw-{api_id}-invoke"
    source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*/ingest/audio"

    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn,
        )
    except ClientError as exc:
        if exc.response["Error"].get("Code") != "ResourceConflictException":
            raise


def deploy(cfg: DeployConfig) -> dict[str, str]:
    session_kwargs = {"region_name": cfg.region} if cfg.region else {}
    session = boto3.Session(**session_kwargs)
    region = cfg.region or session.region_name
    if not region:
        raise ValueError("AWS region could not be determined; set AWS_REGION or pass --region")

    root = Path(__file__).resolve().parent.parent
    zip_bytes = _zip_broker_code(root)

    lambda_client = session.client("lambda")
    apigw_client = session.client("apigatewayv2")
    sts_client = session.client("sts")

    function_description = _ensure_lambda_function(lambda_client, cfg, zip_bytes)
    lambda_arn = function_description["Configuration"]["FunctionArn"]

    api = _find_api_by_name(apigw_client, cfg.api_name)
    if api is None:
        api = apigw_client.create_api(Name=cfg.api_name, ProtocolType="HTTP")
    api_id = api["ApiId"]

    integration_id = _ensure_integration(apigw_client, api_id, lambda_arn)
    _ensure_route(apigw_client, api_id, integration_id)
    _ensure_stage(apigw_client, api_id, cfg.stage_name)

    account_id = sts_client.get_caller_identity()["Account"]
    _allow_apigw_invoke(lambda_client, cfg.function_name, api_id, region, account_id)

    base_url = f"https://{api_id}.execute-api.{region}.amazonaws.com/{cfg.stage_name}"
    ingest_url = f"{base_url}/ingest/audio"
    return {"broker_base_url": base_url, "ingest_url": ingest_url}


def parse_args(argv: Optional[Iterable[str]] = None) -> DeployConfig:
    parser = argparse.ArgumentParser(description="Deploy broker Lambda and API Gateway route")
    parser.add_argument("--function-name", default="marvin-broker", help="Name of the Lambda function to create/update")
    parser.add_argument("--role-arn", required=True, help="IAM role ARN with at least AWSLambdaBasicExecutionRole")
    parser.add_argument("--api-name", default="marvin-broker-api", help="API Gateway HTTP API name")
    parser.add_argument("--stage-name", default="prod", help="Stage name for the API Gateway HTTP API")
    parser.add_argument("--timeout", type=int, default=15, help="Lambda timeout in seconds")
    parser.add_argument("--memory-size", type=int, default=256, help="Lambda memory size in MB")
    parser.add_argument("--region", help="AWS region (falls back to session default)")

    args = parser.parse_args(argv)
    return DeployConfig(
        function_name=args.function_name,
        role_arn=args.role_arn,
        api_name=args.api_name,
        stage_name=args.stage_name,
        timeout=args.timeout,
        memory_size=args.memory_size,
        region=args.region,
    )


def main(argv: Optional[Iterable[str]] = None) -> None:
    cfg = parse_args(argv)
    urls = deploy(cfg)
    print(json.dumps(urls, indent=2))


if __name__ == "__main__":
    main()
