import { signIn } from "next-auth/react";
import { useEffect } from "react";

export default function Signin() {

  useEffect(() => {
    void signIn("auth0", { callbackUrl: "/" });
  });

return <div></div>;
}
