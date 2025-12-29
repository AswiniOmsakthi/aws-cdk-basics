from aws_cdk import (
    Stack,
    SecretValue,
    aws_s3 as s3,
    aws_sagemaker as sagemaker,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as cp_actions,
)
from constructs import Construct

class AwsinfraCdkPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # ==============================
        # Your Application Resources
        # ==============================

        # Create S3 bucket
        bucket = s3.Bucket(self, "InfraBucket")

        # Create SageMaker Domain
        sm_domain = sagemaker.CfnDomain(self, "SageMakerDomain",
            auth_mode="IAM",
            domain_name="my-sagemaker-domain",
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role="arn:aws:iam::257949588515:role/cdk-basic"
            )
        )

        # ==============================
        # Pipeline Definition
        # ==============================

        # Pipeline
        pipeline = codepipeline.Pipeline(
            self, "InfraPipeline",
            pipeline_name="InfraPipeline"
        )

        # 1) Source Stage (Pull from GitHub)
        source_output = codepipeline.Artifact()

        source_action = cp_actions.GitHubSourceAction(
            action_name="GitHub_Source",
            owner="AswiniOmsakthi",                          # GitHub username
            repo="aws-cdk-basics",                           # GitHub repo name
            branch="master",
            oauth_token=SecretValue.secrets_manager("github-token-cdk"),
            output=source_output
        )

        pipeline.add_stage(
            stage_name="Source",
            actions=[source_action]
        )

        # 2) Build Stage (Run CDK synth)
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
                            # synth only the stacks we want
                            "cdk synth"
                        ]
                    }
                },
                "artifacts": {
                    "base-directory": "cdk.out",
                    "files": [
                        "*InfraStack*.template.json"
                    ]
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

        pipeline.add_stage(
            stage_name="Build",
            actions=[build_action]
        )

        # 3) Deploy Stage (CloudFormation stack)
        deploy_action = cp_actions.CloudFormationCreateUpdateStackAction(
            action_name="CFN_Deploy",
            stack_name="AppInfraStack",
            template_path=build_output.at_path("AwsinfraCdkPythonStack.template.json"),
            admin_permissions=True
        )

        pipeline.add_stage(
            stage_name="Deploy",
            actions=[deploy_action]
        )