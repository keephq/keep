// Start policy evaluation logging
print("=== Starting Environment Policy Evaluation ===");

// Get the evaluation instance and extract context and permission
var context = $evaluation.getContext();
var permission = $evaluation.getPermission();
var resource = permission.getResource();

// Get identity information and log
var identity = context.getIdentity();
print("Evaluating policy for user ID: " + identity.getId());

// Get and log resource information
print("Requested resource: " + resource.getName());

// Log requested scopes
var scopes = permission.getScopes();
var scopeNames = [];
for (var i = 0; i < scopes.length; i++) {
  scopeNames.push(scopes[i].getName());
}
print("Requested scopes: " + scopeNames.join(", "));

// Get context attributes for logging
var contextAttributes = context.getAttributes();
print("Client ID: " + contextAttributes.getValue("kc.client.id").asString(0));
print(
  "Client IP: " +
    contextAttributes.getValue("kc.client.network.ip_address").asString(0),
);
print(
  "Request time: " +
    contextAttributes.getValue("kc.time.date_time").asString(0),
);

// Check resource attributes
print("Checking resource attributes...");
var resourceAttributes = resource.getAttributes();
print("Resource attributes type: " + typeof resourceAttributes);

try {
  // Try to get the env attribute directly
  var envAttribute = resourceAttributes.get("env");
  print("Env attribute found: " + (envAttribute !== null));

  if (envAttribute) {
    print("Env attribute value: " + envAttribute);
    var hasDevEnv = envAttribute.contains("dev");
    print("Has dev environment: " + hasDevEnv);

    if (hasDevEnv) {
      print("Environment check passed: env=dev found in resource attributes");
      permission.addClaim("resource_name", resource.getName());
      permission.addClaim(
        "access_reason",
        "Development environment access granted",
      );
      $evaluation.grant();
    } else {
      print("Environment check failed: env value is not 'dev'");
      permission.addClaim(
        "access_reason",
        "Resource is not in development environment",
      );
      $evaluation.deny();
    }
  } else {
    print("No env attribute found");
    permission.addClaim("access_reason", "No environment attribute found");
    $evaluation.deny();
  }
} catch (e) {
  print("Error checking attributes: " + e.message);
  permission.addClaim(
    "access_reason",
    "Error checking environment: " + e.message,
  );
  $evaluation.deny();
}

print("=== Environment Policy Evaluation Complete ===");
