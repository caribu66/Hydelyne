import { FC } from 'react';
import { UserProfile, SpecialistDocument } from '../../types';
import { CertificationBadge } from '../CertificationBadge';
import { DossierCollection } from '../DossierCollection';
import { certificationExpiryStatus } from '../../utils/certificationUtils';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  FileText,
  Loader2,
} from 'lucide-react';

interface DossierCredentialsTabProps {
  profile: UserProfile;
  documents: SpecialistDocument[];
  canManageDocuments: boolean;
  localVerificationOverrides: Record<string, { verificationStatus: string; status?: string }>;
  isVerifying: boolean;
  actionCertId: string | null;
  onVerifyCertification: (certId: string, status: 'VERIFIED' | 'REJECTED') => void | Promise<void>;
  onPreviewDocument: (doc: SpecialistDocument) => void;
}

export const DossierCredentialsTab: FC<DossierCredentialsTabProps> = ({
  profile,
  documents,
  canManageDocuments,
  localVerificationOverrides,
  isVerifying,
  actionCertId,
  onVerifyCertification,
  onPreviewDocument,
}) => {
  const hasPersonalInfo = Boolean(
    profile.countryOfResidence ||
      profile.dateOfBirth ||
      profile.gender ||
      (profile.languages && profile.languages.length > 0) ||
      profile.flyingPoint ||
      profile.nationality,
  );

  return (
    <div className="space-y-4">
      {hasPersonalInfo && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Personal Information
          </h3>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
            {profile.nationality && (
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Nationality</dt>
                <dd className="text-primary text-right">{profile.nationality}</dd>
              </div>
            )}
            {profile.countryOfResidence && (
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Country of residence</dt>
                <dd className="text-primary text-right">{profile.countryOfResidence}</dd>
              </div>
            )}
            {profile.dateOfBirth && (
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Date of birth</dt>
                <dd className="text-primary text-right">{profile.dateOfBirth}</dd>
              </div>
            )}
            {profile.gender && (
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Gender</dt>
                <dd className="text-primary text-right">{profile.gender}</dd>
              </div>
            )}
            {profile.flyingPoint && (
              <div className="flex justify-between gap-2">
                <dt className="text-muted">Flying point</dt>
                <dd className="text-primary text-right">{profile.flyingPoint}</dd>
              </div>
            )}
            {profile.languages && profile.languages.length > 0 && (
              <div className="sm:col-span-2 flex justify-between gap-2">
                <dt className="text-muted">Languages</dt>
                <dd className="text-primary text-right">{profile.languages.join(', ')}</dd>
              </div>
            )}
          </dl>
        </section>
      )}

      {profile.certifications && profile.certifications.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Certifications & Tickets
          </h3>
          <DossierCollection
            items={profile.certifications}
            itemLabel="certifications"
            renderItems={(certifications) => (
              <div className="flex flex-wrap gap-2">
                {certifications.map((cert) => (
                  <CertificationBadge
                    key={cert}
                    certification={cert}
                    verified={profile.certificationDetails?.some(
                      (detail) => detail.name === cert && detail.verificationStatus === 'verified',
                    )}
                    size="md"
                  />
                ))}
              </div>
            )}
          />
        </section>
      )}

      {profile.certificationDetails && profile.certificationDetails.length > 0 && (
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
              Completion & Expiry
            </h3>
            <span className="text-xs text-muted font-mono">
              {profile.certificationDetails.length} recorded
            </span>
          </div>
          <DossierCollection
            items={profile.certificationDetails}
            itemLabel="credentials"
            renderItems={(certifications) => (
              <div className="space-y-2">
                {certifications.map((cert) => {
                  const effectiveVerification =
                    localVerificationOverrides[cert.id]?.verificationStatus ??
                    cert.verificationStatus ??
                    'unverified';
                  const effectiveStatus =
                    localVerificationOverrides[cert.id]?.status ?? cert.status;
                  const expiryStatus = certificationExpiryStatus(cert.expiryDate);
                  const displayStatus =
                    effectiveStatus === 'rejected'
                      ? effectiveStatus
                      : expiryStatus === 'expired' || expiryStatus === 'expiring_soon'
                        ? expiryStatus
                        : expiryStatus === 'invalid'
                          ? 'invalid'
                        : effectiveStatus;

                  const linkedDoc = documents.find(
                    (d) =>
                      d.id === cert.documentRef ||
                      (d.category === 'certificate' &&
                        d.title.toLowerCase().includes(cert.name.toLowerCase())),
                  );

                  return (
                    <div
                      key={cert.id}
                      className="rounded-[10px] border border-border-subtle bg-canvas/40 p-3 transition-colors hover:border-border-strong"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2.5">
                        <div className="space-y-1 min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-sm text-primary">
                              {cert.name}
                            </span>
                            {cert.certNumber && (
                              <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-surface-raised text-secondary border border-border-subtle">
                                #{cert.certNumber}
                              </span>
                            )}
                            {effectiveVerification === 'verified' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-positive/10 text-positive border border-positive/20">
                                <CheckCircle2 className="w-3 h-3" />
                                Verified
                              </span>
                            ) : effectiveVerification === 'rejected' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-negative/10 text-negative border border-negative/20">
                                <XCircle className="w-3 h-3" />
                                Rejected
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-warning/10 text-warning border border-warning/20">
                                <AlertCircle className="w-3 h-3" />
                                Pending Verification
                              </span>
                            )}
                            {displayStatus === 'expired' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-negative/10 text-negative border border-negative/20">
                                Expired
                              </span>
                            )}
                            {displayStatus === 'expiring_soon' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-warning/10 text-warning border border-warning/20">
                                Expiring Soon
                              </span>
                            )}
                            {displayStatus === 'invalid' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium font-mono bg-warning/10 text-warning border border-warning/20">
                                <AlertCircle className="w-3 h-3" />
                                Invalid expiry date
                              </span>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted">
                            {cert.issuingBody && (
                              <span>
                                Issued by{' '}
                                <strong className="text-secondary font-normal">
                                  {cert.issuingBody}
                                </strong>
                              </span>
                            )}
                            <span>
                              {cert.issueDate ? `Completed ${cert.issueDate}` : 'Date not recorded'}
                            </span>
                            <span>
                              {cert.expiryDate ? `Expires ${cert.expiryDate}` : 'No expiry recorded'}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {linkedDoc && (
                            <button
                              type="button"
                              onClick={() => onPreviewDocument(linkedDoc)}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-border-subtle bg-surface hover:bg-surface-raised text-secondary hover:text-primary transition-colors focus-visible:ring-2 focus-visible:ring-focus cursor-pointer"
                              title={`View backing document (${linkedDoc.fileName})`}
                            >
                              <FileText className="w-3.5 h-3.5 text-accent" />
                              <span>View Proof</span>
                            </button>
                          )}

                          {canManageDocuments && (
                            <div className="flex items-center gap-1">
                              {effectiveVerification !== 'verified' && (
                                <button
                                  type="button"
                                  disabled={isVerifying && actionCertId === cert.id}
                                  onClick={() => void onVerifyCertification(cert.id, 'VERIFIED')}
                                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg bg-positive/15 text-positive hover:bg-positive/25 border border-positive/30 transition-colors focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer"
                                  title="Verify this certification"
                                >
                                  {isVerifying && actionCertId === cert.id ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <CheckCircle2 className="w-3 h-3" />
                                  )}
                                  <span>Verify</span>
                                </button>
                              )}

                              {effectiveVerification !== 'rejected' && (
                                <button
                                  type="button"
                                  disabled={isVerifying && actionCertId === cert.id}
                                  onClick={() => void onVerifyCertification(cert.id, 'REJECTED')}
                                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-lg bg-surface hover:bg-negative/10 text-muted hover:text-negative border border-border-subtle hover:border-negative/30 transition-colors focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50 cursor-pointer"
                                  title="Reject this certification"
                                >
                                  <XCircle className="w-3 h-3" />
                                  <span>Reject</span>
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          />
        </section>
      )}

      {profile.trainingDetails && profile.trainingDetails.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Training / Qualifications
          </h3>
          <DossierCollection
            items={profile.trainingDetails}
            itemLabel="qualifications"
            renderItems={(training) => (
              <div className="space-y-2">
                {training.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-border-subtle bg-canvas/40 px-3 py-2"
                  >
                    <div className="flex flex-col">
                      <span className="text-primary">{item.name}</span>
                      {item.location && (
                        <span className="text-xs text-muted">{item.location}</span>
                      )}
                    </div>
                    <span className="text-muted text-sm">
                      {item.completedDate
                        ? `Completed ${item.completedDate.slice(0, 4)}`
                        : 'Completion date not recorded'}
                      {item.expiryDate ? ` · Expires ${item.expiryDate.slice(0, 4)}` : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          />
        </section>
      )}

      {profile.education && (
        <section>
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Education
          </h3>
          <p className="mt-1 text-secondary">{profile.education}</p>
        </section>
      )}
    </div>
  );
};
