#!/bin/bash
function deploy_kms(){
    echo -e "\n\nDeploying ${1}..."
    aws cloudformation deploy \
        --template-file ${2} \
        --stack-name ${1} \
        --parameter-overrides \
            KMSAdmin=${username}
}

function set_secure_ssm(){
    kmsID=$(aws cloudformation describe-stacks --stack-name ${3} --query "Stacks[].Outputs[].OutputValue[]" --output text | awk '{print $2}')
    echo -e "\nSetting SSM for ${1}"

    aws ssm put-parameter --cli-input-json '{"Type": "SecureString", "KeyId": "'"${kmsID}"'", "Name": "'"${1}"'", "Value": "'"${2}"'"}' --overwrite
}

function set_ssm(){
    echo -e "\nSetting ${3} SSM for ${1} with ${2}"
    aws ssm put-parameter --name ${1} \
        --value "${2}" \
        --type ${3} \
        --description "${4}" \
        --overwrite
}

function deploy_bucket(){
    echo -e "\n\nDeploying s3 bucket..."
    aws cloudformation deploy \
        --template-file ./ConfigBucket.json \
        --stack-name GoldenAMIConfigBucket
}

function deploy_pipeline(){
    echo -e "\n\nDeploying AMI PipelineStack..."
    aws cloudformation deploy \
        --template-file ./final.json \
        --stack-name GoldenAMIPipeline \
        --parameter-overrides \
            ApproverUserIAMARN=${approverARN} \
            EmailID=${emailID} \
            MetadataJSON='{"Account_ID_1":"region_1,region_2"}' \
            VPC=${vpcID} \
            buildVersion="1" \
            continuousInspectionFrequency="rate(30 days)" \
            instanceType="t2.large" \
            productName="ProductName-ProductVersion" \
            productOSAndVersion="OperatingSystemName-OperatingSystemVersion" \
            roleName="goldenAMICrossAccountRole" \
            subnetPrivate=${subnetPrivate} \
        --s3-bucket $(aws cloudformation describe-stacks --stack-name GoldenAMIConfigBucket --query "Stacks[].Outputs[].OutputValue" --output text) \
        --capabilities CAPABILITY_NAMED_IAM
    echo -e "\nCheck Codepipeline to view the status of deployment..."
    echo -e "Wait until script is fully finished executing..."
}

function zip_and_upload_to_s3(){
    zip -9 ${1}.zip ${1}.py
    aws s3 cp ${1}.zip s3://$(aws cloudformation describe-stacks --stack-name GoldenAMIConfigBucket --query "Stacks[].Outputs[].OutputValue" --output text)/${1}.zip

}

# Global variables
team="Security"
message="INFO: You are about to input sensitive data; your input will not be echo'd back to the terminal"

# KMS config
kmsStack="InsightVMKMS"
read -p "AWS username to administer the KMS key (e.g. bob@matson.com): " username

# # InsightVM API user config
insightvmUser=$(echo INSIGHTVM_USERNAME)
insightvmPass=$(echo INSIGHTVM_PASSWORD)
insightvmEngine=$(echo INSIGHTVM_ENGINE_ID)
echo -e "\n${message}"
read -sp "Insightvm API username: " apiUser

echo -e ""
read -sp "Insightvm API password: " apiPass

echo -e "\n"
read -p "The engine ID used to as the scanner: " engineID

#Pipeline config
echo -e ""
read -p "IAM user ARN of the Golden AMI approver. (e.g. arn:aws:iam::1234567890:user/bob@matson.com) " approverARN

echo -e ""
read -p "Your email address for receiving Inspector assessment results and golden AMI creation notification: " emailID

echo -e ""
read -p "The VPC ID of env that this will be launched in: " vpcID

echo -e ""
read -p "Subnet ID: " subnetPrivate

### Main ###
deploy_kms ${kmsStack} ./InsightVMKMSKey.json
set_secure_ssm  ${insightvmUser} ${apiUser} ${kmsStack}
set_secure_ssm ${insightvmPass} ${apiPass} ${kmsStack}
set_ssm ${insightvmEngine} ${engineID} "String" "The engine ID used to as the scanner"
deploy_bucket
zip_and_upload_to_s3 RunScan
zip_and_upload_to_s3 SetupContinuousAssessment
aws s3 cp simpleEC2-SSMParamInput.json s3://$(aws cloudformation describe-stacks --stack-name GoldenAMIConfigBucket --query "Stacks[].Outputs[].OutputValue" --output text)/simpleEC2-SSMParamInput.json
deploy_pipeline

# clean up
rm *.zip