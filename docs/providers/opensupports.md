# OpenSupports Provider

OpenSupports is an open-source ticket system. This provider allows Keep to push alerts as tickets into OpenSupports.

## Authentication

To connect Keep to OpenSupports, you need:
- **Host**: The base URL of your OpenSupports installation.
- **Email**: Your OpenSupports account email.
- **Password**: Your OpenSupports account password.

## Functionality

The provider currently supports creating tickets.

### Actions

#### `notify`
Creates a new ticket in OpenSupports.

**Parameters:**
- `subject` (required): The subject of the ticket.
- `content` (required): The body content of the ticket.
- `department_id` (optional): The ID of the department (default: \"1\").
- `priority_id` (optional): The ID of the priority level (default: \"1\").
