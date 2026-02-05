# Instructions for setup

1. Open your aws console.
2. Search for `Amazon OpenSearch Service`
3. In the sidebar navigate to `Serverless` > `Dashboard`.
4. Click `Create Collection` > 
   1. Fill `Name` & `Description`.
   2. Select Collection Type `Search`
   3. Security :`Standard Create`
   4. Encryption: `Use AWS owned key`
   5. Access collections from : `Public`
   6. Resource type: Select both Checkboxes.
5. Next
6. `Add principals` > `IAM User and Roles` > Select a User of your choice.
7. Grant access to Index : `Create Index`, `Read documents` & `Write or update documents`.
8. Enter a random policy name.
9. Submit
10. Wait for the deployment to be complete.
11. Meanwhile go to IAM.
12. Go to Access Management > Users > Click the user you selected in step 6.
13. Create a access key and download/save it.
14. Go to Add permission > Create inline policy > JSON 
    Paste this
    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "iam:SimulatePrincipalPolicy",
                    "aoss:GetAccessPolicy",
                    "aoss:APIAccessAll",
                    "aoss:ListAccessPolicies"
                ],
                "Resource": "*"
            }
        ]
    }
    ```
15. Click Next > Give a Policy name > Save.
16. Go back to your collection and copy the `OpenSearch endpoint` This is your Domain.
