ALERTS = [
    {
        "build": {
            "buildId": "12345",
            "buildName": "Run Tests",
            "buildTypeName": "Run Tests",
            "buildTypeId": "MyProject_RunTests",
            "projectName": "MyProject",
            "branchName": "main",
            "buildResult": "FAILED",
            "buildStatusMessage": "Tests failed: 3 tests out of 47 failed",
            "buildUrl": "https://teamcity.example.com/viewLog.html?buildId=12345",
        }
    },
    {
        "build": {
            "buildId": "12346",
            "buildName": "Deploy to Staging",
            "buildTypeName": "Deploy to Staging",
            "buildTypeId": "MyProject_DeployStaging",
            "projectName": "MyProject",
            "branchName": "develop",
            "buildResult": "FAILED",
            "buildStatusMessage": "Deployment script exited with code 1: health check failed",
            "buildUrl": "https://teamcity.example.com/viewLog.html?buildId=12346",
        }
    },
    {
        "build": {
            "buildId": "12347",
            "buildName": "Build and Package",
            "buildTypeName": "Build and Package",
            "buildTypeId": "MyProject_Build",
            "projectName": "MyProject",
            "branchName": "feature/new-api",
            "buildResult": "SUCCESS",
            "buildStatusMessage": "Build successful",
            "buildUrl": "https://teamcity.example.com/viewLog.html?buildId=12347",
        }
    },
]
