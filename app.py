#!/usr/bin/env python3
import aws_cdk as cdk
from awsinfra_cdk_python.awsinfra_cdk_python_stack import AwsinfraCdkPythonStack

app = cdk.App()

AwsinfraCdkPythonStack(
    app,
    "AwsinfraCdkPythonStack",
    env=cdk.Environment(
        account="257949588515",
        region="us-east-1"
    )
)

app.synth()