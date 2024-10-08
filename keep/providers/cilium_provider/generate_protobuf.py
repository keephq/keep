import os
import subprocess

# Create directories for the proto files
os.makedirs("hubble_proto/google/protobuf", exist_ok=True)
os.makedirs("hubble_proto/flow", exist_ok=True)
os.makedirs("hubble_proto/relay", exist_ok=True)

# Download the necessary proto files
proto_files = [
    (
        "https://raw.githubusercontent.com/cilium/cilium/master/api/v1/flow/flow.proto",
        "hubble_proto/flow/flow.proto",
    ),
    (
        "https://raw.githubusercontent.com/cilium/cilium/master/api/v1/observer/observer.proto",
        "hubble_proto/observer.proto",
    ),
    (
        "https://raw.githubusercontent.com/cilium/cilium/master/api/v1/relay/relay.proto",
        "hubble_proto/relay/relay.proto",
    ),
    (
        "https://raw.githubusercontent.com/protocolbuffers/protobuf/master/src/google/protobuf/timestamp.proto",
        "hubble_proto/google/protobuf/timestamp.proto",
    ),
    (
        "https://raw.githubusercontent.com/protocolbuffers/protobuf/master/src/google/protobuf/duration.proto",
        "hubble_proto/google/protobuf/duration.proto",
    ),
    (
        "https://raw.githubusercontent.com/protocolbuffers/protobuf/master/src/google/protobuf/wrappers.proto",
        "hubble_proto/google/protobuf/wrappers.proto",
    ),
]

for proto_url, proto_path in proto_files:
    subprocess.run(["curl", "-o", proto_path, proto_url])

# Generate Python code from proto files
subprocess.run(
    [
        "python",
        "-m",
        "grpc_tools.protoc",
        "-I",
        "hubble_proto",
        "--python_out=.",
        "--grpc_python_out=.",
        "hubble_proto/flow/flow.proto",
        "hubble_proto/observer.proto",
        "hubble_proto/relay/relay.proto",
    ]
)

print("gRPC Python client generation completed.")
