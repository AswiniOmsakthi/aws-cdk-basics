from aws_cdk import (
    Stack,
    SecretValue,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as cp_actions
)
from constructs import Construct


class AwsinfraCdkPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ==========================
        # 1) Networking --> VPC
        # ==========================
        vpc = ec2.Vpc(self, "InfraVPC", max_azs=2)

        # ==========================
        # 2) IAM Role --> SageMaker Execution
        # ==========================
        sagemaker_exec_role = iam.Role(
            self, "SageMakerExecRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com")
        )
        # Optional: attach policies you want
        sagemaker_exec_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSageMakerFullAccess"
            )
        )

        # ==========================
        # 3) S3 Bucket
        # ==========================
        bucket = s3.Bucket(self, "InfraBucket")

        # ==========================
        # 4) SageMaker Studio Domain
        # ==========================
        sm_domain = sagemaker.CfnDomain(
            self, "SageMakerDomain",
            auth_mode="IAM",
            domain_name="my-sagemaker-domain",
            vpc_id=vpc.vpc_id,
            subnet_ids=[subnet.subnet_id for subnet in vpc.private_subnets],
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=sagemaker_exec_role.role_arn
            )
        )

        # ==========================
        # 5) CI/CD Pipeline Definition
        # ==========================

        # Pipeline
        pipeline = codepipeline.Pipeline(
            self, "InfraPipeline",
            pipeline_name="InfraPipeline"
        )

        # ---- Source Stage (GitHub) ----
        source_output = codepipeline.Artifact()
        source_action = cp_actions.GitHubSourceAction(
            action_name="GitHub_Source",
            owner="AswiniOmsakthi",       # Replace with your GitHub username
            repo="aws-cdk-basics",        # Replace with your repository name
            branch="master",
            oauth_token=SecretValue.secrets_manager("github-token-cdk"),
            output=source_output
        )
        pipeline.add_stage(stage_name="Source", actions=[source_action])

        # ---- Build Stage (synth) ----
        build_project = codebuild.PipelineProject(
            self, "CDK_Build_Project",
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_7_0
            ),
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "phases": {
                    "install": {
                        "commands": [
                            "npm install -g aws-cdk",
                            "pip install -r requirements.txt"
                        ]
                    },
                    "build": {
                        "commands": [
                            # Generate CloudFormation templates
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

        build_output = codepipeline.Artifact()
        build_action = cp_actions.CodeBuildAction(
            action_name="CDK_Synth",
            project=build_project,
            input=source_output,
            outputs=[build_output]
        )
        pipeline.add_stage(stage_name="Build", actions=[build_action])

        # ---- Deploy Stage ----
        deploy_action = cp_actions.CloudFormationCreateUpdateStackAction(
            action_name="CFN_Deploy",
            stack_name="AppInfraStack",
            template_path=build_output.at_path("AwsinfraCdkPythonStack.template.json"),
            admin_permissions=True
        )
        pipeline.add_stage(stage_name="Deploy", actions=[deploy_action])
