// ModalContext.tsx
import React, { createContext, useState, useContext, ReactNode } from 'react';

interface ModalContextType {
  modals: Record<string, boolean>;
  openModal: (key: string) => void;
  closeModal: (key: string) => void;
}

const ModalContext = createContext<ModalContextType>({
  modals: {},
  openModal: () => {},
  closeModal: () => {},
});

interface ModalProviderProps {
  children: ReactNode;
}

export const ModalProvider: React.FC<ModalProviderProps> = ({ children }) => {
  const [modals, setModals] = useState<Record<string, boolean>>({});

  const openModal = (key: string) => {
    setModals(prev => ({ ...prev, [key]: true }));
  };

  const closeModal = (key: string) => {
    setModals(prev => ({ ...prev, [key]: false }));
  };

  return (
    <ModalContext.Provider value={{ modals, openModal, closeModal }}>
      {children}
    </ModalContext.Provider>
  );
};

export const useModal = () => useContext(ModalContext);
