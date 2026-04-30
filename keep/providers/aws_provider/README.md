# AWS Provider

Query AWS infrastructure resources — ECS clusters/tasks, Application Load Balancers (ALBs), target groups, and EC2 instances — directly from Keep workflows.

## Authentication

| Field | Required | Notes |
|---|---|---|
| `region` | Yes | AWS region, e.g. `us-east-1` |
| `access_key_id` | No | Leave empty when running on EC2/ECS with an IAM role |
| `secret_access_key` | No | Leave empty when running on EC2/ECS with an IAM role |
| `session_token` | No | Only needed for temporary/assumed-role credentials |

## IAM Permissions

Attach a policy with the permissions you need:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:ListClusters",
        "ecs:DescribeClusters",
        "ecs:ListTasks",
        "ecs:DescribeTasks",
        "elasticloadbalancing:DescribeLoadBalancers",
        "elasticloadbalancing:DescribeTargetGroups",
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

## Workflow Usage

### Query ECS clusters

```yaml
steps:
  - name: list-clusters
    provider:
      type: aws
      config: "{{ providers.my-aws }}"
      with:
        resource: ecs_clusters
```

### Query running ECS tasks in a specific cluster

```yaml
steps:
  - name: running-tasks
    provider:
      type: aws
      config: "{{ providers.my-aws }}"
      with:
        resource: ecs_tasks
        cluster: my-cluster
        desired_status: RUNNING
```

### Query Application Load Balancers

```yaml
steps:
  - name: list-albs
    provider:
      type: aws
      config: "{{ providers.my-aws }}"
      with:
        resource: load_balancers
```

### Query target groups for an ALB

```yaml
steps:
  - name: target-groups
    provider:
      type: aws
      config: "{{ providers.my-aws }}"
      with:
        resource: target_groups
        load_balancer_arn: "arn:aws:elasticloadbalancing:us-east-1:123456789:loadbalancer/app/my-alb/abc123"
```

### Query EC2 instances

```yaml
steps:
  - name: ec2-instances
    provider:
      type: aws
      config: "{{ providers.my-aws }}"
      with:
        resource: ec2_instances
        instance_ids:
          - i-0abc123def456
```

## Supported `resource` values

| Value | API calls | Description |
|---|---|---|
| `ecs_clusters` | `ListClusters` + `DescribeClusters` | All ECS clusters in the region |
| `ecs_tasks` | `ListTasks` + `DescribeTasks` | Tasks across all clusters (or a specific one) |
| `load_balancers` | `DescribeLoadBalancers` | All ALBs/NLBs in the region |
| `target_groups` | `DescribeTargetGroups` | Target groups (optionally filtered by LB ARN) |
| `ec2_instances` | `DescribeInstances` | EC2 instances (optionally filtered by IDs) |

## Links

- [Closes #4889](https://github.com/keephq/keep/issues/4889)
