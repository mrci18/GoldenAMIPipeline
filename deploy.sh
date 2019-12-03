#!/bin/bash
function deploy_kms(){
    echo -e "\n\nDeploying ${1}..."
    aws cloudformation deploy \
        --template-file ${2} \
        --stack-name ${1} \
        --parameter-overrides \
            Service=${service} \
            Team=${team} User=${username}
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
# Global variables
team="Security"
message="INFO: You are about to input sensitive data; your input will not be echo'd back to the terminal"

# KMS config
kmsStack="InsightVMKMS"
read -p "AWS username running this script (e.g. bob@matson.com): " username

# InsightVM API user config
insightvmUser=$(echo INSIGHTVM_USERNAME)
insightvmPass=$(echo INSIGHTVM_PASSWORD)
insightvmEngine=$(echo INSIGHTVM_ENGINE_ID)
echo -e "\n${message}"
read -sp "The insightvm API username: " apiUser

echo -e "\n${message}"
read -sp "The password of the insightvm user: " apiPass

echo -e ""
read -p "The engine ID used to as the scanner" engineID

# Run functions
deploy_kms ${kmsStack} ./InsightVMKMSKey.json
set_secure_ssm  ${insightvmUser} ${apiUser} ${kmsStack}
set_secure_ssm ${insightvmPass} ${apiPass} ${kmsStack}
set_ssm ${insightvmPass} ${engineID} "String" "The engine ID used to as the scanner"