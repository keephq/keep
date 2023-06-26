import React, { ReactNode } from "react";
import ErrorComponent from "./error";
import {KeepApiError} from "./error";


interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  errorMessage?: string;
  errorUrl?: string;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);

    // Define a state variable to track whether there is an error or not
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: any) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error: KeepApiError, errorInfo: any) {
    // You can use your own error logging service here
    console.log({ error, errorInfo });

    // Set the error and URL in the component state
    this.setState({
      hasError: true,
      errorMessage: error.toString(),
      errorUrl: error.url, // or any other URL you want to capture
    });
  }


  render() {
    // Check if an error has occurred
    if (this.state.hasError) {
      // Render custom fallback UI
      return (
        <ErrorComponent errorMessage={this.state.errorMessage!} url={this.state.errorUrl!} />
      );
    }

    // Return children components in case of no error
    return this.props.children;
  }
}

export default ErrorBoundary;
