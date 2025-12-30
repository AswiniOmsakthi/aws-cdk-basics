#!/usr/bin/env python3
import aws_cdk as cdk
from awsinfra_cdk_python.awsinfra_cdk_python_stack import AwsinfraCdkPythonStack, ApplicationStack

app = cdk.App()

# Pipeline Infrastructure Stack
AwsinfraCdkPythonStack(
    app,
    "AwsinfraCdkPythonStack",
    env=cdk.Environment(
        account="257949588515",
        region="us-east-1"
    )
)

# Application Infrastructure Stack (deployed by pipeline)
ApplicationStack(
    app,
    "ApplicationStack",
    env=cdk.Environment(
        account="257949588515",
        region="us-east-1"
    )
)

app.synth()