"use client";

import { Ban, Check, Copy, HardDriveDownload, KeyRound, MoreHorizontal, RotateCw, ShieldAlert, Trash2, UserCheck, UserPlus, Users } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/AppShell";
import { AuditLogCard } from "@/components/AuditLogCard";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, IconButton } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useConfirm } from "@/components/ui/ConfirmDialog";
import { Dialog } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field, Input } from "@/components/ui/Input";
import { Menu } from "@/components/ui/Menu";
import { Select } from "@/components/ui/Select";
import { EmptyRow, SkeletonRows, Table, TableWrap } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import { adminBackupBlob, adminDeleteUser, adminInvite, adminListUsers, adminResetPassword, adminUpdateUser } from "@/lib/api";
import { ROLES, ROLE_META } from "@/lib/constants";
import { formatDate, formatRelative, initials } from "@/lib/format";
import type { InviteResponse, Role, UserProfile } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { copyToClipboard, downloadBlob, errorMessage } from "@/lib/utils";

/** A one-time temporary password to show: from an invite or a reset (copy differs). */
interface TempPasswordState {
  result: InviteResponse;
  mode: "invite" | "reset";
}

export default function UsersPage() {
  const { profile, isAdmin } = useUser();
  const toast = useToast();
  const confirm = useConfirm();

  const [users, setUsers] = useState<UserProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [tempPassword, setTempPassword] = useState<TempPasswordState | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [backingUp, setBackingUp] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setUsers(await adminListUsers());
    } catch (err) {
      setError(errorMessage(err));
      setUsers([]);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) void load();
  }, [isAdmin, load]);

  if (!isAdmin) {
    return (
      <div>
        <PageHeader title="Users" />
        <Card>
          <EmptyState icon={<ShieldAlert />} title="Admins only" description="User management is restricted to administrators." />
        </Card>
      </div>
    );
  }

  const update = async (u: UserProfile, patch: Parameters<typeof adminUpdateUser>[1], okMsg: string) => {
    setBusyId(u.id);
    try {
      const next = await adminUpdateUser(u.id, patch);
      setUsers((prev) => (prev ? prev.map((x) => (x.id === u.id ? next : x)) : prev));
      toast.success(okMsg);
    } catch (err) {
      toast.error("Update failed", errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (u: UserProfile) => {
    const ok = await confirm({
      title: `Remove ${u.full_name || u.email}?`,
      message: "They will lose access immediately. Their jobs are kept.",
      confirmLabel: "Remove user",
      danger: true,
      onConfirm: async () => {
        await adminDeleteUser(u.id);
      },
    });
    if (ok) {
      setUsers((prev) => (prev ? prev.filter((x) => x.id !== u.id) : prev));
      toast.success("User removed");
    }
  };

  const resetPassword = async (u: UserProfile) => {
    await confirm({
      title: `Reset password for ${u.full_name || u.email}?`,
      message: "A new temporary password is generated and shown once. Their current password stops working immediately and they must choose a new one at next sign-in.",
      confirmLabel: "Reset password",
      onConfirm: async () => {
        setBusyId(u.id);
        try {
          const res = await adminResetPassword(u.id);
          setUsers((prev) => (prev ? prev.map((x) => (x.id === u.id ? res.profile : x)) : prev));
          setTempPassword({ result: res, mode: "reset" });
        } catch (err) {
          toast.error("Could not reset password", errorMessage(err));
          throw err;
        } finally {
          setBusyId(null);
        }
      },
    });
  };

  const backup = async () => {
    setBackingUp(true);
    try {
      const { blob, filename } = await adminBackupBlob();
      downloadBlob(blob, filename);
      toast.success("Backup downloaded", filename);
    } catch (err) {
      toast.error("Could not download the backup", errorMessage(err));
    } finally {
      setBackingUp(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Users"
        description="Invite engineers and reviewers, manage roles and access."
        actions={
          <>
            <Button variant="secondary" leftIcon={<HardDriveDownload />} onClick={() => void backup()} loading={backingUp} title="Consistent SQLite snapshot of jobs, users and standards">
              Download database backup
            </Button>
            <Button leftIcon={<UserPlus />} onClick={() => setInviteOpen(true)}>
              Invite user
            </Button>
          </>
        }
      />

      {error ? (
        <Alert tone="danger" title="Could not load users" className="mb-6" actions={<Button size="sm" variant="secondary" onClick={() => void load()}>Retry</Button>}>
          {error}
        </Alert>
      ) : null}

      <Card className="overflow-hidden">
        <TableWrap flush>
          <Table>
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last sign-in</th>
                <th>Created</th>
                <th className="w-12" />
              </tr>
            </thead>
            <tbody>
              {users === null ? (
                <SkeletonRows rows={4} cols={6} />
              ) : users.length === 0 ? (
                <EmptyRow colSpan={6}>
                  <EmptyState compact icon={<Users />} title="No users" description="Invite your first colleague." />
                </EmptyRow>
              ) : (
                users.map((u) => {
                  const isSelf = u.id === profile?.id;
                  const busy = busyId === u.id;
                  return (
                    <tr key={u.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-ink text-[11.5px] font-semibold text-white">
                            {initials(u.full_name, u.email)}
                          </span>
                          <div className="min-w-0">
                            <p className="truncate font-medium text-ink">
                              {u.full_name || "—"}
                              {isSelf ? <span className="ml-1.5 text-[11px] font-normal text-muted">(you)</span> : null}
                            </p>
                            <p className="truncate text-[12px] text-muted">{u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="w-36">
                          <Select
                            size="sm"
                            value={u.role}
                            disabled={isSelf || busy}
                            aria-label={`Role for ${u.email}`}
                            onChange={(e) => void update(u, { role: e.target.value as Role }, `Role updated to ${ROLE_META[e.target.value as Role].label}`)}
                            options={ROLES.map((r) => ({ value: r, label: ROLE_META[r].label }))}
                          />
                        </div>
                      </td>
                      <td>
                        {u.is_active ? (
                          <Badge tone="success" dot>
                            Active
                          </Badge>
                        ) : (
                          <Badge tone="neutral" icon={<Ban />}>
                            Deactivated
                          </Badge>
                        )}
                        {u.must_set_password ? (
                          <Badge tone="warning" icon={<KeyRound />} className="ml-1.5" title="Has not set their own password yet">
                            Temp password
                          </Badge>
                        ) : null}
                      </td>
                      <td className="text-[12.5px] text-muted" title={formatDate(u.last_sign_in_at)}>
                        {u.last_sign_in_at ? formatRelative(u.last_sign_in_at) : "Never"}
                      </td>
                      <td className="text-[12.5px] text-muted">{formatDate(u.created_at)}</td>
                      <td>
                        {!isSelf ? (
                          <Menu
                            items={[
                              u.is_active
                                ? { key: "deactivate", label: "Deactivate", icon: <Ban />, onSelect: () => void update(u, { is_active: false }, "User deactivated") }
                                : { key: "activate", label: "Activate", icon: <UserCheck />, onSelect: () => void update(u, { is_active: true }, "User activated") },
                              { key: "reset", label: "Reset password", icon: <RotateCw />, onSelect: () => void resetPassword(u) },
                              { key: "remove", label: "Remove user", icon: <Trash2 />, danger: true, separator: true, onSelect: () => void remove(u) },
                            ]}
                            trigger={({ toggle }) => (
                              <IconButton label="More actions" size="xs" onClick={toggle} loading={busy}>
                                <MoreHorizontal />
                              </IconButton>
                            )}
                          />
                        ) : null}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </Table>
        </TableWrap>
      </Card>

      <AuditLogCard className="mt-6" />

      <InviteDialog
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onInvited={(res) => {
          setInviteOpen(false);
          setUsers((prev) => (prev ? [res.profile, ...prev.filter((x) => x.id !== res.profile.id)] : [res.profile]));
          setTempPassword({ result: res, mode: "invite" });
        }}
      />
      <TempPasswordDialog state={tempPassword} onClose={() => setTempPassword(null)} />
    </div>
  );
}

function InviteDialog({ open, onClose, onInvited }: { open: boolean; onClose: () => void; onInvited: (res: InviteResponse) => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("engineer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setEmail("");
    setName("");
    setRole("engineer");
    setError(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await adminInvite({ email: email.trim(), full_name: name.trim() || null, role });
      reset();
      onInvited(res);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (busy) return;
        reset();
        onClose();
      }}
      locked={busy}
      title="Invite a user"
      description="A temporary password is generated and shown once. Share it with them securely."
      icon={<UserPlus />}
    >
      <form onSubmit={submit} className="space-y-4 pt-1">
        {error ? (
          <Alert tone="danger" title="Could not invite">
            {error}
          </Alert>
        ) : null}
        <Field label="Email" required>
          {(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@avighnagroup.com" required autoFocus />}
        </Field>
        <Field label="Full name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" />}</Field>
        <Field label="Role" required hint={ROLE_META[role].description}>
          {(id) => <Select id={id} value={role} onChange={(e) => setRole(e.target.value as Role)} options={ROLES.map((r) => ({ value: r, label: ROLE_META[r].label }))} />}
        </Field>
        <div className="flex justify-end gap-2 pt-1">
          <Button
            variant="secondary"
            onClick={() => {
              reset();
              onClose();
            }}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button type="submit" loading={busy} disabled={!email}>
            Send invite
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function TempPasswordDialog({ state, onClose }: { state: TempPasswordState | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  const result = state?.result ?? null;
  const isReset = state?.mode === "reset";

  useEffect(() => {
    if (!state) setCopied(false);
  }, [state]);

  const copy = async () => {
    if (!result) return;
    const ok = await copyToClipboard(result.temporary_password);
    if (ok) {
      setCopied(true);
      toast.success("Temporary password copied");
    } else {
      toast.error("Could not copy — select the text and copy manually");
    }
  };

  return (
    <Dialog
      open={!!state}
      onClose={onClose}
      title={isReset ? "New temporary password" : "Temporary password"}
      description={
        isReset
          ? "Shown once. Their previous password no longer works; they will be asked to set a new one at next sign-in."
          : "Shown once. The user will be asked to set their own password on first sign-in."
      }
      icon={<KeyRound />}
      footer={<Button onClick={onClose}>Done</Button>}
    >
      {result ? (
        <div className="space-y-4 pt-1">
          <div className="rounded-card border border-line bg-surface-2 px-4 py-3">
            <p className="text-[12px] text-muted">Account</p>
            <p className="text-[13.5px] font-medium text-ink">{result.profile.full_name || result.profile.email}</p>
            <p className="text-[12.5px] text-muted">
              {result.profile.email} · {ROLE_META[result.profile.role].label}
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-card border border-brand/30 bg-brand-tint px-4 py-3">
            <code className="tnum flex-1 select-all break-all font-mono text-[16px] font-semibold tracking-wide text-ink">{result.temporary_password}</code>
            <Button variant={copied ? "secondary" : "primary"} size="sm" leftIcon={copied ? <Check /> : <Copy />} onClick={() => void copy()}>
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <Alert tone="warning">
            {isReset
              ? "This password cannot be retrieved later. If it is lost, reset it again."
              : "This password cannot be retrieved later. If it is lost, reset their password from the user menu."}
          </Alert>
        </div>
      ) : null}
    </Dialog>
  );
}
