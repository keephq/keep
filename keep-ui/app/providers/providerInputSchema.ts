import * as Yup from 'yup';

export const providerInputSchema = Yup.object().shape({
  provider_name: Yup.string().required('Provider name is required'),
  url: Yup.string()
    .url('Invalid URL format')
    .matches(/^(https?:\/\/)?(localhost|[\w.-]+)(:\d+)?\/?$/, 'URL must be in a valid format')
    .required('URL is required'),
  host: Yup.string()
    .matches(/^[a-zA-Z0-9.-]+$/, 'Invalid host format')
    .required('Host is required'),
  port: Yup.number()
    .min(1, 'Port number must be between 1 and 65535')
    .max(65535, 'Port number must be between 1 and 65535'),
  // Add any other fields as necessary
});
