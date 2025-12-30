from aws_cdk import (
    Stack,
    SecretValue,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
    aws_ec2 as ec2,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as cp_actions
)
from constructs import Construct
import time

class AwsinfraCdkPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        timestamp = int(time.time())

        # Import existing default VPC
        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)
        subnet_ids = [subnet.subnet_id for subnet in vpc.public_subnets]

        # IAM Role for CodeBuild
        codebuild_role = iam.Role(
            self,
            "CodeBuildExecutionRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com")
        )

        codebuild_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "cloudformation:*",
                "sagemaker:*",
                "s3:*",
                "ec2:*",
                "iam:PassRole",
                "iam:GetRole",
                "logs:*",
                "codeartifact:*",
                "sts:AssumeRole"
            ],
            resources=["*"]
        ))

        # IAM Role for CloudFormation
        cfn_role = iam.Role(
            self,
            "CloudFormationRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("cloudformation.amazonaws.com"),
                iam.ServicePrincipal("codepipeline.amazonaws.com")
            )
        )

        cfn_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "s3:*",
                "sagemaker:*",
                "ec2:*",
                "iam:*",
                "logs:*",
                "cloudformation:*"
            ],
            resources=["*"]
        ))

        # IAM Role for SageMaker
        sagemaker_exec_role = iam.Role.from_role_arn(
            self,
            "ExistingSageMakerRole",
            role_arn="arn:aws:iam::257949588515:role/cdk-basic",
            mutable=False
        )

        # S3 Bucket with unique name
        s3.Bucket(
            self,
            "InfraBucket",
            bucket_name=f"infra-bucket-{self.account}-{self.region}-{timestamp}",
            versioned=True
        )

        # SageMaker Studio Domain with unique name
        sagemaker.CfnDomain(
            self,
            "SageMakerDomain",
            domain_name=f"sagemaker-domain-{timestamp}",
            auth_mode="IAM",
            vpc_id=vpc.vpc_id,
            subnet_ids=subnet_ids,
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=sagemaker_exec_role.role_arn
            )
        )

        # CI/CD Pipeline
        pipeline = codepipeline.Pipeline(
            self,
            "InfraPipeline",
            pipeline_name="InfraPipeline"
        )

        # Stage 1: Source
        source_output = codepipeline.Artifact()
        pipeline.add_stage(
            stage_name="Source",
            actions=[
                cp_actions.GitHubSourceAction(
                    action_name="GitHub_Source",
                    owner="AswiniOmsakthi",
                    repo="aws-cdk-basics",
                    branch="master",
                    oauth_token=SecretValue.secrets_manager("github-token-cdk"),
                    output=source_output
                )
            ]
        )

        # Stage 2: Build
        build_output = codepipeline.Artifact()
        build_project = codebuild.PipelineProject(
            self,
            "CDK_Build_Project",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "commands": [
                            "echo 'Installing dependencies...'",
                            "npm install -g aws-cdk",
                            "pip install -r requirements.txt"
                        ]
                    },
                    "build": {
                        "commands": [
                            "echo 'Running CDK Synth...'",
                            "cdk synth"
                        ]
                    }
                },
                "artifacts": {
                    "base-directory": "cdk.out",
                    "files": ["*.template.json"]
                }
            })
        )

        pipeline.add_stage(
            stage_name="Build",
            actions=[
                cp_actions.CodeBuildAction(
                    action_name="CDK_Synth",
                    project=build_project,
                    input=source_output,
                    outputs=[build_output]
                )
            ]
        )

        # Stage 3: Deploy
        pipeline.add_stage(
            stage_name="Deploy",
            actions=[
                cp_actions.CloudFormationCreateUpdateStackAction(
                    action_name="CFN_Deploy",
                    stack_name="AppInfraStack",
                    template_path=build_output.at_path(
                        "AwsinfraCdkPythonStack.template.json"
                    ),
                    admin_permissions=True,
                    role=cfn_role
                )
            ]
        )