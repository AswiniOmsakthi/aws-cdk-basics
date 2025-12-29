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


class AwsinfraCdkPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------
        # Lookup the Default VPC
        # -------------------------------------
        vpc = ec2.Vpc.from_lookup(self, "DefaultVPC", is_default=True)

        public_subnet_ids = [subnet.subnet_id for subnet in vpc.public_subnets]

        # -------------------------------------
        # IAM Role for SageMaker
        # -------------------------------------
        sagemaker_exec_role = iam.Role.from_role_arn(
            self, "ExistingSageMakerRole",
            role_arn="arn:aws:iam::257949588515:role/cdk-basic",
            mutable=False
        )

        # -------------------------------------
        # S3 Bucket
        # -------------------------------------
        bucket = s3.Bucket(self, "InfraBucket")

        # -------------------------------------
        # SageMaker Studio Domain (with VPC)
        # -------------------------------------
        sm_domain = sagemaker.CfnDomain(
            self, "SageMakerDomain",
            auth_mode="IAM",
            domain_name="my-sagemaker-domain",
            vpc_id=vpc.vpc_id,
            subnet_ids=public_subnet_ids,
            default_user_settings=sagemaker.CfnDomain.UserSettingsProperty(
                execution_role=sagemaker_exec_role.role_arn
            )
        )

        # -------------------------------------
        # CI/CD Pipeline
        # -------------------------------------
        pipeline = codepipeline.Pipeline(
            self, "InfraPipeline",
            pipeline_name="InfraPipeline"
        )

        # — Source Stage (GitHub) —
        source_output = codepipeline.Artifact()
        source_action = cp_actions.GitHubSourceAction(
            action_name="GitHub_Source",
            owner="AswiniOmsakthi",               # GitHub user
            repo="aws-cdk-basics",                # GitHub repo
            branch="master",                      # or "main"
            oauth_token=SecretValue.secrets_manager("github-token-cdk"),
            output=source_output
        )
        pipeline.add_stage(
            stage_name="Source",
            actions=[source_action]
        )

        # — Build Stage (CodeBuild running CDK synth) —
        build_output = codepipeline.Artifact()
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
                        "commands": ["cdk synth"]
                    }
                },
                "artifacts": {
                    "base-directory": "cdk.out",
                    "files": ["*.template.json"]
                }
            })
        )
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

        # — Deploy Stage (CloudFormation) —
        deploy_action = cp_actions.CloudFormationCreateUpdateStackAction(
            action_name="CFN_Deploy",
            stack_name="AppInfraStack",
            template_path=build_output.at_path(
                "AwsinfraCdkPythonStack.template.json"
            ),
            admin_permissions=True
        )
        pipeline.add_stage(
            stage_name="Deploy",
            actions=[deploy_action]
        )