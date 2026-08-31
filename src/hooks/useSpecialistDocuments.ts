import { useState, useEffect, useCallback } from 'react';
import { SpecialistDocument, DocumentCategory } from '../types';

const STORAGE_KEY = 'hydenlyne_specialist_documents_v1';

// Seed default documents for existing mock profiles
const DEFAULT_DOCUMENTS: Record<string, SpecialistDocument[]> = {
  'p-1': [
    {
      id: 'doc-p1-1',
      title: 'OPITO BOSIET with CA-EBS',
      category: 'certificate',
      fileName: 'Alistair_MacIntyre_BOSIET_CAEBS.pdf',
      fileSize: '1.4 MB',
      issueDate: '2024-06-12',
      expiryDate: '2028-06-12',
      isVerified: true,
      uploadedAt: '2025-01-15T10:30:00Z',
      notes: 'OPITO Reference: #OP-882941. Valid for North Sea, UKCS & Norwegian waters.',
    },
    {
      id: 'doc-p1-2',
      title: 'OEUK Offshore Medical Assessment',
      category: 'medical',
      fileName: 'Alistair_OEUK_Medical_2025.pdf',
      fileSize: '820 KB',
      issueDate: '2025-01-08',
      expiryDate: '2027-01-08',
      isVerified: true,
      uploadedAt: '2025-01-15T10:32:00Z',
      notes: 'Fit for offshore deployment without restriction. Includes audiometry.',
    },
    {
      id: 'doc-p1-3',
      title: 'Senior MMO & PAM Executive CV & Track Record',
      category: 'cv',
      fileName: 'Dr_Alistair_MacIntyre_Executive_CV.pdf',
      fileSize: '2.1 MB',
      issueDate: '2025-02-01',
      isVerified: true,
      uploadedAt: '2025-02-01T14:00:00Z',
      notes: '60+ offshore seismic & wind farm deployments summarized with vessel specs.',
    },
    {
      id: 'doc-p1-4',
      title: 'JNCC Marine Mammal Observer Certification',
      category: 'certificate',
      fileName: 'JNCC_MMO_Accreditation_AM.pdf',
      fileSize: '650 KB',
      issueDate: '2022-04-10',
      isVerified: true,
      uploadedAt: '2025-01-15T10:35:00Z',
    },
  ],
  'p-2': [
    {
      id: 'doc-p2-1',
      title: 'IOGP / IMCA Geophysical Client Rep Endorsement',
      category: 'certificate',
      fileName: 'Sarah_VanDerBerg_IOGP_Rep_Cert.pdf',
      fileSize: '1.9 MB',
      issueDate: '2023-09-14',
      expiryDate: '2027-09-14',
      isVerified: true,
      uploadedAt: '2025-01-18T09:15:00Z',
      notes: 'Endorsed for 4D OBN seismic survey supervision and quality management.',
    },
    {
      id: 'doc-p2-2',
      title: 'OPITO BOSIET with CA-EBS & MIST',
      category: 'certificate',
      fileName: 'Sarah_VDB_BOSIET_Valid.pdf',
      fileSize: '1.2 MB',
      issueDate: '2024-03-20',
      expiryDate: '2028-03-20',
      isVerified: true,
      uploadedAt: '2025-01-18T09:20:00Z',
    },
    {
      id: 'doc-p2-3',
      title: 'OEUK Offshore Medical Certificate',
      category: 'medical',
      fileName: 'Sarah_OEUK_Medical.pdf',
      fileSize: '740 KB',
      issueDate: '2024-11-10',
      expiryDate: '2026-11-10',
      isVerified: true,
      uploadedAt: '2025-01-18T09:22:00Z',
    },
    {
      id: 'doc-p2-4',
      title: 'Geophysical QC Consultant CV & Seismic Track Record',
      category: 'cv',
      fileName: 'Sarah_VanDerBerg_Consultant_CV.pdf',
      fileSize: '2.4 MB',
      issueDate: '2025-01-20',
      isVerified: true,
      uploadedAt: '2025-01-20T11:00:00Z',
    },
  ],
  'p-3': [
    {
      id: 'doc-p3-1',
      title: 'GWO Basic Safety Training (BST) Offshore Wind',
      category: 'certificate',
      fileName: 'Gareth_Evans_GWO_BST_Package.pdf',
      fileSize: '1.6 MB',
      issueDate: '2024-05-18',
      expiryDate: '2026-05-18',
      isVerified: true,
      uploadedAt: '2025-01-10T08:30:00Z',
      notes: 'First Aid, Manual Handling, Fire Awareness, Working at Heights & Sea Survival.',
    },
    {
      id: 'doc-p3-2',
      title: 'OEUK Offshore Medical & Chester Step',
      category: 'medical',
      fileName: 'Gareth_Evans_OEUK_Medical.pdf',
      fileSize: '890 KB',
      issueDate: '2024-08-01',
      expiryDate: '2026-08-01',
      isVerified: true,
      uploadedAt: '2025-01-10T08:32:00Z',
    },
    {
      id: 'doc-p3-3',
      title: 'Offshore Geotechnical Specialist CV',
      category: 'cv',
      fileName: 'Gareth_Evans_Geotech_CV_2025.pdf',
      fileSize: '1.8 MB',
      issueDate: '2025-01-12',
      isVerified: true,
      uploadedAt: '2025-01-12T16:20:00Z',
    },
  ],
  'p-4': [
    {
      id: 'doc-p4-1',
      title: 'PAMGUARD Advanced Bioacoustics Operator Certificate',
      category: 'certificate',
      fileName: 'Helena_Lindqvist_PAMGUARD_Cert.pdf',
      fileSize: '1.1 MB',
      issueDate: '2023-11-05',
      isVerified: true,
      uploadedAt: '2025-01-22T13:10:00Z',
    },
    {
      id: 'doc-p4-2',
      title: 'Norwegian Continental Shelf (NCS) Safety & CA-EBS',
      category: 'certificate',
      fileName: 'Helena_NCS_Safety_Valid.pdf',
      fileSize: '1.5 MB',
      issueDate: '2024-02-14',
      expiryDate: '2028-02-14',
      isVerified: true,
      uploadedAt: '2025-01-22T13:12:00Z',
    },
    {
      id: 'doc-p4-3',
      title: 'Bioacoustician & PAM Consultant CV',
      category: 'cv',
      fileName: 'Helena_Lindqvist_CV.pdf',
      fileSize: '1.9 MB',
      issueDate: '2025-01-25',
      isVerified: true,
      uploadedAt: '2025-01-25T10:00:00Z',
    },
  ],
};

export function getDocumentComplianceStatus(doc: SpecialistDocument): {
  status: 'valid' | 'expiring_soon' | 'expired' | 'no_expiry';
  daysLeft?: number;
  label: string;
  badgeClass: string;
} {
  if (!doc.expiryDate) {
    return {
      status: 'no_expiry',
      label: 'Verified Permanent',
      badgeClass: 'bg-zinc-800 text-zinc-300 border-zinc-700',
    };
  }

  const now = new Date();
  const expiry = new Date(doc.expiryDate);
  const diffTime = expiry.getTime() - now.getTime();
  const daysLeft = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (daysLeft < 0) {
    return {
      status: 'expired',
      daysLeft,
      label: `Expired (${Math.abs(daysLeft)}d ago)`,
      badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    };
  }

  if (daysLeft <= 90) {
    return {
      status: 'expiring_soon',
      daysLeft,
      label: `Expiring Soon (${daysLeft}d left)`,
      badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    };
  }

  return {
    status: 'valid',
    daysLeft,
    label: `Valid (${Math.floor(daysLeft / 30)} mo remaining)`,
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  };
}

export function useSpecialistDocuments() {
  const [documentsByProfile, setDocumentsByProfile] = useState<Record<string, SpecialistDocument[]>>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {
      // Fallback
    }
    return DEFAULT_DOCUMENTS;
  });

  // Save to localStorage when changed
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(documentsByProfile));
    } catch {
      // ignore
    }
  }, [documentsByProfile]);

  const getDocumentsForProfile = useCallback((profileId: string): SpecialistDocument[] => {
    return documentsByProfile[profileId] || DEFAULT_DOCUMENTS[profileId] || [];
  }, [documentsByProfile]);

  const addDocument = useCallback((
    profileId: string,
    document: Omit<SpecialistDocument, 'id' | 'uploadedAt'>
  ): SpecialistDocument => {
    const newDoc: SpecialistDocument = {
      ...document,
      id: `doc-custom-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      uploadedAt: new Date().toISOString(),
      isVerified: document.isVerified ?? true,
    };

    setDocumentsByProfile((prev) => {
      const existing = prev[profileId] || DEFAULT_DOCUMENTS[profileId] || [];
      return {
        ...prev,
        [profileId]: [newDoc, ...existing],
      };
    });

    return newDoc;
  }, []);

  const removeDocument = useCallback((profileId: string, documentId: string) => {
    setDocumentsByProfile((prev) => {
      const existing = prev[profileId] || DEFAULT_DOCUMENTS[profileId] || [];
      return {
        ...prev,
        [profileId]: existing.filter((d) => d.id !== documentId),
      };
    });
  }, []);

  return {
    getDocumentsForProfile,
    addDocument,
    removeDocument,
  };
}
