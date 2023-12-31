import { Dialog } from '@headlessui/react';
import { useState } from 'react';
import Select, { components, SingleValue, MenuListProps} from 'react-select';
import { TextInput, Button, Subtitle } from '@tremor/react';
import { AuthenticationType } from "utils/authenticationType";

interface RoleOption {
    value: string;
    label: string | JSX.Element;
    tooltip?: string;
    isDisabled?: boolean;
  }

interface AddUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (email: string, role: string, password: string) => void;
  authType: string;
}

export default function AddUserModal({ isOpen, onClose, onSubmit, authType }: AddUserModalProps) {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [selectedRole, setSelectedRole] = useState<SingleValue<RoleOption>>(null);
  const [password, setPassword] = useState('');
  const [hoveredOption, setHoveredOption] = useState<string | null>(null);

  let roleOptions: RoleOption[] = [
    { value: 'admin', label: 'Admin', tooltip: "Admin has read/write/update/delete for every resource" },
    { value: 'noc', label: 'NOC', tooltip: "NOC has the ability to view alerts and assign to alerts" },
    { value: 'create_new', label: 'Create custom role', isDisabled: true, tooltip: "For custom roles, contact Keep team" },
];


const CustomOption = (props: any) => {
    const isHovered = hoveredOption === props.data.value;
    const tooltipContent = props.data.tooltip;

    return (
        <div
            onMouseEnter={() => setHoveredOption(props.data.value)}
            onMouseLeave={() => setHoveredOption(null)}
            className="relative"
        >
            <components.Option {...props} />
            {isHovered && tooltipContent && (
                <div className="absolute z-50 w-auto p-2 bg-gray-700 text-white text-sm rounded-md shadow-lg -translate-x-1/2 left-1/2 top-0 mt-[-40px]">
                    {tooltipContent}
                </div>
            )}
        </div>
    );
};





  const validateEmail = (email: string) => {
    const re = /\S+@\S+\.\S+/;
    return re.test(email);
  };

  const isFormValid = () => {
    return validateEmail(email) && selectedRole && (authType !== AuthenticationType.SINGLE_TENANT || password);
  };

  const handleSubmit = (e: React.FormEvent) => {
    console.log("handleSubmit");
    e.preventDefault();
    if (!validateEmail(email)) {
      setEmailError('Please enter a valid email address.');
      return;
    }
    setEmailError('');
    if (selectedRole) {
      onSubmit(email, selectedRole.value, password);
      // clear form
      setEmail('');
      setSelectedRole(null);
      setPassword('');
      onClose();
    }
  };

  return (
    <Dialog as="div" className="fixed inset-0 z-10 overflow-y-auto" open={isOpen} onClose={onClose}>
      <div className="flex items-center justify-center min-h-screen">
        <Dialog.Panel className="bg-white p-4 rounded" style={{ width: '400px', maxWidth: '90%' }}>
          <Dialog.Title>Add User</Dialog.Title>
                <form onSubmit={handleSubmit}>
                    <div className="mt-4">
                    <Subtitle>Email</Subtitle>
                    <TextInput value={email} onChange={e => setEmail(e.target.value)} />
                    {emailError && <p className="text-red-500 text-sm">{emailError}</p>}
                    </div>
                    <div className="mt-4">
                        <Subtitle>Role</Subtitle>
                        <Select
                            options={roleOptions}
                            onChange={option => setSelectedRole(option)}
                            className="mt-2"
                            placeholder="Select role"
                            components={{ Option: CustomOption }}
                        />
                    </div>

                    {authType === AuthenticationType.SINGLE_TENANT && (
                        <div className="mt-4">
                            <Subtitle>Password</Subtitle>
                            <TextInput type="password" value={password} onChange={e => setPassword(e.target.value)} />
                        </div>
                    )}
                    <div className="mt-6 flex gap-2">
                        <Button color="orange" type="submit" disabled={!isFormValid()}>Add User</Button>
                        <Button onClick={onClose} variant="secondary" className="border border-orange-500 text-orange-500">Cancel</Button>
                    </div>
                </form>
                </Dialog.Panel>
            </div>
    </Dialog>
  );
}
