from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    SecretValue
)
from constructs import Construct

class AwsinfraCdkPythonStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # example resource
        # queue = sqs.Queue(
        #     self, "AwsinfraCdkPythonQueue",
        #     visibility_timeout=Duration.seconds(300),
        # )
        # Create a CodeBuild project
        build_project = codebuild.PipelineProject(
            self, 'HelloWorldBuild',
            build_spec=codebuild.BuildSpec.from_object({
                'version': '0.2',
                'phases': {
                    'build': {
                        'commands': [
                            'echo "Starting build process..."',
                            'echo "Hello, AswiniOmsakthi! Updated at $(date)" >> hello.txt',
                            'echo "Current content of hello.txt:"',
                            'cat hello.txt'
                        ]
                    }
                },
                'artifacts': {
                    'files': ['hello.txt']
                }
            }),
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_5_0
            )
        )

        # Create a CodePipeline
        pipeline = codepipeline.Pipeline(
            self, 'HelloWorldPipeline',
            pipeline_name='HelloWorldPipeline'
        )

        # Source stage
        source_output = codepipeline.Artifact()
        source_action = codepipeline_actions.GitHubSourceAction(
            action_name='GitHub_Source',
            owner='AswiniOmsakthi',  # Replace with your GitHub username
            repo='aws-cdk-basics',  # Replace with your repository name
            branch='main',
            oauth_token=SecretValue.secrets_manager('github-token-cdk'),
            output=source_output
        )

        pipeline.add_stage(
            stage_name='Source',
            actions=[source_action]
        )

        # Build stage
        build_output = codepipeline.Artifact()
        build_action = codepipeline_actions.CodeBuildAction(
            action_name='CodeBuild',
            project=build_project,
            input=source_output,
            outputs=[build_output]
        )

        pipeline.add_stage(
            stage_name='Build',
            actions=[build_action]
        )
