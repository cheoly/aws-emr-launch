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

import enum

from typing import Optional, Mapping, Dict, List
from abc import abstractmethod

from aws_cdk import (
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    core
)


class StepFailureAction(enum.Enum):
    TERMINATE_JOB_FLOW = 'TERMINATE_JOB_FLOW'
    TERMINATE_CLUSTER = 'TERMINATE_CLUSTER'
    CANCEL_AND_WAIT = 'CANCEL_AND_WAIT'
    CONTINUE = 'CONTINUE'


class Bindable:
    @abstractmethod
    def bind_scope(self, scope: core.Construct) -> Mapping[str, any]:
        ...


class Code(Bindable):
    @staticmethod
    def from_path(path: str, deployment_bucket: s3.Bucket, deployment_prefix: str):
        return EmrCode(s3_deployment.BucketDeploymentProps(
            sources=[s3_deployment.Source.asset(path)],
            destination_bucket=deployment_bucket,
            destination_key_prefix=deployment_prefix))

    @staticmethod
    def from_props(deployment_props: s3_deployment.BucketDeploymentProps):
        return EmrCode(deployment_props)

    @property
    @abstractmethod
    def s3_path(self) -> str:
        ...


class EmrCode(Code):
    def __init__(self, deployment_props: s3_deployment.BucketDeploymentProps, id: Optional[str] = None):
        self._deployment_props = deployment_props
        self._deployment_bucket = deployment_props.destination_bucket
        self._deployment_prefix = deployment_props.destination_key_prefix
        self._id = id
        self._bucket_deployment = None

    def bind_scope(self, scope: core.Construct) -> Mapping[str, any]:
        # If the same deployment is used multiple times, retain only the first instantiation
        if self._bucket_deployment is None:
            # Convert BucketDeploymentProps to dict
            deployment_props = vars(self._deployment_props)['_values']
            self._bucket_deployment = s3_deployment.BucketDeployment(
                scope,
                f'BucketDeployment_{self._id}' if self._id else 'BucketDeployment',
                **deployment_props)

        return {'S3Path': self.s3_path}

    @property
    def s3_path(self) -> str:
        return f's3://{self._deployment_bucket.bucket_name}/{self._deployment_prefix}'


class EmrBootstrapAction(Bindable):
    def __init__(self, name: str, path: str, args: Optional[List[str]] = None, code: Optional[EmrCode] = None):
        self._name = name
        self._path = path
        self._args = args
        self._code = code

    def bind_scope(self, scope: core.Construct) -> Mapping[str, any]:
        if self._code is not None:
            self._code.bind_scope(scope)

        return {
            'Name': self._name,
            'ScriptBootstrapAction': {
                'Path': self._path,
                'Args': self._args if self._args else []
            }
        }


class EmrStep(Bindable):
    def __init__(self, name: str, jar: str, main_class: Optional[str] = None, args: Optional[List[str]] = None,
                 action_on_failure: StepFailureAction = StepFailureAction.CONTINUE,
                 properties: Optional[List[Dict]] = None, code: Optional[EmrCode] = None):
        self._name = name
        self._jar = jar
        self._main_class = main_class
        self._args = args
        self._action_on_failure = action_on_failure
        self._properties = properties
        self._code = code

    def bind_scope(self, scope: core.Construct):
        if self._code is not None:
            self._code.bind_scope(scope)

        return {
            'Name': self._name,
            'ActionOnFailure': self._action_on_failure.name,
            'HadoopJarStep': {
                'Jar': self._jar,
                'MainClass': self._main_class,
                'Args': self._args if self._args else [],
                'Properties': self._properties if self._properties else []
            }
        }
