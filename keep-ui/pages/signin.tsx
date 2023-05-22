// @ts-nocheck
import { signIn } from "next-auth/react";

const Signin = () => {
  // Since we currently only use auth0
  void signIn("auth0");
};

export default Signin;
