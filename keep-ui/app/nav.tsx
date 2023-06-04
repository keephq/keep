import Navbar from './navbar';
import { getServerSession } from '../utils/customAuth';
import { authOptions } from '../pages/api/auth/[...nextauth]';

export default async function Nav() {
  const session = await getServerSession(authOptions);
  return <Navbar session={session} />;
}
