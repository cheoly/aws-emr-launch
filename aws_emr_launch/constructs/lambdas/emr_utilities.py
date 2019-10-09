# Copyright 2019 Amazon.com, Inc. and its affiliates. All Rights Reserved.
#
# Licensed under the Amazon Software License (the 'License').
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#
#   http://aws.amazon.com/asl/
#
# or in the 'license' file accompanying this file. This file is distributed
# on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

import json

from typing import Optional
from . import _lambda_path

from aws_cdk import (
    aws_lambda,
    aws_iam as iam,
    aws_sns as sns,
    aws_stepfunctions as sfn,
    core
)


class EMRUtilitiesStack(core.Stack):

    def __init__(self, props: core.StackProps):
        stack_props = props.__dict__.get('_values', {})
        super().__init__(**stack_props)

        self._step_function_lambdas = StepFunctionLambdas(
            self, 'EMRUtilitiesStack_StepFunctionLambdas')
        self._emr_config_utils_layer = aws_lambda.LayerVersion(
            self, 'EMRUtilitiesStack_EMRConfigUtilsLayer',
            code=aws_lambda.Code.asset(_lambda_path('layers/emr_config_utils')),
            compatible_runtimes=[
                aws_lambda.Runtime(name="python3.7", supports_inline_code=True)
            ],
            description=''
        )

    @property
    def step_function_lambdas(self):
        return self._step_function_lambdas


class StepFunctionLambdas(core.Construct):

    def __init__(self, scope: core.Construct, id: str) -> None:
        super().__init__(scope, id)

        code = aws_lambda.Code.asset(_lambda_path('emr_utilities'))

        self._run_job_flow = aws_lambda.Function(
            self,
            'StepFunctionLambdas_AddJobFlow',
            code=code,
            handler='run_job_flow.handler',
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=core.Duration.minutes(5),
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        'elasticmapreduce:RunJobFlow',
                        'elasticmapreduce:ListClusters',
                        'elasticmapreduce:ListSteps'
                    ],
                    resources=['*']
                )
            ]
        )

        self._add_job_flow_steps = aws_lambda.Function(
            self,
            'StepFunctionLambdas_AddJobFlowSteps',
            code=code,
            handler='add_job_flow_steps.handler',
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=core.Duration.minutes(5),
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        'elasticmapreduce:AddJobFlowSteps'
                    ],
                    resources=['*']
                )
            ]
        )

        self._check_step_status = aws_lambda.Function(
            self,
            'StepFunctionLambdas_CheckStepStatus',
            code=code,
            handler='check_step_status.handler',
            runtime=aws_lambda.Runtime.PYTHON_3_7,
            timeout=core.Duration.minutes(5),
            initial_policy=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        'elasticmapreduce:DescribeCluster',
                        'elasticmapreduce:DescribeStep',
                        'cloudwatch:PutMetricData'
                    ],
                    resources=['*']
                )
            ]
        )

    @property
    def run_job_flow(self) -> aws_lambda.Function:
        return self._run_job_flow

    @property
    def add_job_flow_steps(self) -> aws_lambda.Function:
        return self._add_job_flow_steps

    @property
    def check_step_status(self) -> aws_lambda.Function:
        return self._check_step_status


class LaunchEMRConfigLambda(aws_lambda.Function):

    def __init__(self, scope: core.Construct, id: str, *, props: aws_lambda.FunctionProps,
                 step_function: sfn.StateMachine,
                 cluster_config: dict,
                 step_function_wait_time: Optional[int] = 60,
                 fail_if_job_running: Optional[bool] = False,
                 success_topic: Optional[sns.Topic] = None,
                 failure_topic: Optional[sns.Topic] = None):

        environment = {
            'DEFAULT_STEP_FUNCTION_ARN': step_function.state_machine_arn,
            'DEFAULT_CLUSTER_CONFIG': json.dumps(cluster_config),
            'DEFAULT_STEP_FUNCTION_WAIT_TIME': str(step_function_wait_time),
            'DEFAULT_FAIL_IF_JOB_RUNNING': str(fail_if_job_running),
        }

        if success_topic:
            environment['DEFAULT_SUCCESS_TOPIC_ARN'] = success_topic.topic_arn
        if failure_topic:
            environment['DEFAULT_FAILURE_TOPIC_ARN'] = failure_topic.topic_arn

        function_props = props.__dict__.get('_values', {})
        function_props['environment'] = dict(function_props.get('environment', {}), **environment)

        super().__init__(scope, id, **function_props)
