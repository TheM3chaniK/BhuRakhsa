"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import PageHeader from "@/components/ui/PageHeader";
import Stamp from "@/components/ui/Stamp";
import { api } from "@/lib/api";
import { AreaResponse, OfficerDetailResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

export default function AdminOfficersPage() {
  const { user } = useAuth();

  const [officers, setOfficers] = useState<OfficerDetailResponse[]>([]);
  const [areas, setAreas] = useState<AreaResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  // Create Officer Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createEmail, setCreateEmail] = useState("");
  const [createPassword, setCreatePassword] = useState("Officer@12345678!");
  const [createPhone, setCreatePhone] = useState("+91");
  const [createAreaId, setCreateAreaId] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  // Edit Officer Modal State
  const [editOfficer, setEditOfficer] = useState<OfficerDetailResponse | null>(null);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);

  // Assign Area Modal State
  const [assignOfficerTarget, setAssignOfficerTarget] = useState<OfficerDetailResponse | null>(null);
  const [selectedAssignAreaId, setSelectedAssignAreaId] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch all officers
      const offRes = await api.listAdminOfficers({ page: 1, page_size: 50 });
      if (offRes.items) {
        setOfficers(offRes.items);
      }

      // 2. Fetch available geographical areas
      const areaRes = await api.listAreas();
      if (areaRes.items) {
        setAreas(areaRes.items);
        if (areaRes.items.length > 0) {
          setCreateAreaId(areaRes.items[0].id);
          setSelectedAssignAreaId(areaRes.items[0].id);
        }
      }
    } catch (err: any) {
      console.error("Failed to load officers/areas:", err);
      setError(err.message || "Failed to load admin officer directory.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user]);

  // Handle Create Officer
  const handleCreateOfficer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createName.trim() || !createEmail.trim() || !createPassword.trim()) {
      setError("Please fill in name, email, and password.");
      return;
    }

    setIsCreating(true);
    setError(null);
    setSuccessNotice(null);

    try {
      const newOfficer = await api.createAdminOfficer({
        full_name: createName.trim(),
        email: createEmail.trim(),
        password: createPassword,
        phone: createPhone.trim() || undefined,
      });

      // If initial area was selected, assign it
      if (createAreaId && newOfficer.id) {
        try {
          await api.assignOfficerArea(newOfficer.id, createAreaId);
        } catch {}
      }

      setSuccessNotice(`Area Officer '${newOfficer.full_name}' provisioned successfully!`);
      setShowCreateModal(false);
      setCreateName("");
      setCreateEmail("");
      setCreatePhone("+91");
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to create Area Officer.");
    } finally {
      setIsCreating(false);
    }
  };

  // Handle Update Officer
  const handleUpdateOfficer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editOfficer) return;

    setIsUpdating(true);
    setError(null);
    setSuccessNotice(null);

    try {
      await api.updateAdminOfficer(editOfficer.id, {
        full_name: editName.trim(),
        phone: editPhone.trim() || undefined,
        is_active: editIsActive,
      });

      setSuccessNotice(`Officer profile for '${editName}' updated successfully.`);
      setEditOfficer(null);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to update officer.");
    } finally {
      setIsUpdating(false);
    }
  };

  // Handle Assign Area
  const handleAssignArea = async () => {
    if (!assignOfficerTarget || !selectedAssignAreaId) return;

    setIsAssigning(true);
    try {
      await api.assignOfficerArea(assignOfficerTarget.id, selectedAssignAreaId);
      setSuccessNotice(`Jurisdiction assigned to ${assignOfficerTarget.full_name}.`);
      setAssignOfficerTarget(null);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to assign area.");
    } finally {
      setIsAssigning(false);
    }
  };

  // Handle Remove Area
  const handleRemoveArea = async (officerId: string, areaId: string, officerName: string) => {
    if (!confirm(`Are you sure you want to unassign this area from ${officerName}?`)) return;

    try {
      await api.removeOfficerArea(officerId, areaId);
      setSuccessNotice(`Area assignment removed from ${officerName}.`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to remove area assignment.");
    }
  };

  // Handle Delete / Demote Officer
  const handleDeleteOfficer = async (officer: OfficerDetailResponse) => {
    const action = confirm(
      `Are you sure you want to delete/deactivate Area Officer '${officer.full_name}'?\n\nThis will revoke their review permissions and area jurisdiction access.`
    );
    if (!action) return;

    try {
      await api.updateAdminOfficer(officer.id, { is_active: false });
      setSuccessNotice(`Area Officer '${officer.full_name}' has been deactivated.`);
      await loadData();
    } catch (err: any) {
      setError(err.message || "Failed to deactivate officer.");
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-10 py-14">
      <PageHeader
        step="System Administration"
        title="Area Officer Management &amp; Jurisdictional Provisioning"
        description="Create, update, deactivate, and assign dedicated geographical revenue jurisdictions to Area Verification Officers."
      />

      {/* Header Action & Metrics Toolbar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded border border-line bg-paper-dark/50 p-4">
        <div>
          <h3 className="font-serif text-sm font-semibold text-ink">
            👨‍💼 Active Officer Directory ({officers.length} registered)
          </h3>
          <p className="text-xs text-ink-soft mt-0.5">
            Super Administrator console for assigning Hatgacha, Bakultala, and regional blocks.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="rounded border border-line bg-paper px-3 py-1.5 text-xs font-mono text-ink hover:bg-paper-dark"
          >
            ↻ Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="rounded bg-ink px-4 py-1.5 text-xs font-medium text-paper hover:bg-ink/90 shadow-sm"
          >
            + Provision New Area Officer
          </button>
        </div>
      </div>

      {successNotice && (
        <div className="mb-6 rounded border border-verified/40 bg-verified/10 px-4 py-3 text-xs text-verified font-medium">
          ✓ {successNotice}
        </div>
      )}

      {error && (
        <div className="mb-6 rounded border border-risk/40 bg-risk/10 px-4 py-3 text-xs text-risk font-medium">
          ✕ {error}
        </div>
      )}

      {/* Officers Table */}
      {loading ? (
        <div className="rounded border border-line bg-paper-dark/20 p-12 text-center text-xs font-mono text-ink-soft">
          Loading Area Officer directory from PostgreSQL...
        </div>
      ) : officers.length === 0 ? (
        <div className="rounded border border-line bg-paper-dark/20 p-12 text-center">
          <p className="font-serif text-lg text-ink">No Area Officers provisioned</p>
          <p className="mt-1 text-xs text-ink-soft">
            Click "+ Provision New Area Officer" to register the first officer account.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded border border-line">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-paper-dark/60 text-[11px] uppercase tracking-wide text-ink-soft">
                <th className="px-4 py-2.5 font-medium">Officer Name &amp; Role</th>
                <th className="px-4 py-2.5 font-medium">Contact Details</th>
                <th className="px-4 py-2.5 font-medium">Dedicated Jurisdictions</th>
                <th className="px-4 py-2.5 font-medium">Account Status</th>
                <th className="px-4 py-2.5 font-medium text-right">Admin Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {officers.map((off) => (
                <tr key={off.id} className="bg-paper-dark/20 hover:bg-paper-dark/40">
                  {/* Name & Role */}
                  <td className="px-4 py-3.5">
                    <p className="font-semibold text-xs text-ink">{off.full_name}</p>
                    <span className="font-mono text-[10px] text-ink-soft">UUID: {off.id.slice(0, 8)}</span>
                  </td>

                  {/* Contact */}
                  <td className="px-4 py-3.5 text-xs">
                    <p className="font-mono text-ink">{off.email}</p>
                    <p className="text-[11px] text-ink-soft mt-0.5">{off.phone || "No phone registered"}</p>
                  </td>

                  {/* Assigned Areas */}
                  <td className="px-4 py-3.5 text-xs">
                    {off.assigned_areas && off.assigned_areas.length > 0 ? (
                      <div className="flex flex-wrap items-center gap-1.5">
                        {off.assigned_areas.map((area) => (
                          <span
                            key={area.id}
                            className="inline-flex items-center gap-1 rounded bg-brass/10 border border-brass/40 px-2 py-0.5 text-[11px] font-medium text-ink"
                          >
                            📍 {area.name} ({area.code})
                            <button
                              onClick={() => handleRemoveArea(off.id, area.id, off.full_name)}
                              className="text-risk font-bold ml-1 hover:text-risk/80"
                              title="Remove jurisdiction"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-[11px] text-risk italic">No areas assigned</span>
                    )}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3.5">
                    <Stamp tone={off.is_active ? "verified" : "risk"}>
                      {off.is_active ? "ACTIVE" : "INACTIVE"}
                    </Stamp>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3.5 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => {
                          setAssignOfficerTarget(off);
                        }}
                        className="rounded border border-line bg-paper px-2.5 py-1 text-xs font-medium text-ink hover:bg-paper-dark"
                        title="Assign new geographical area"
                      >
                        + Assign Area
                      </button>
                      <button
                        onClick={() => {
                          setEditOfficer(off);
                          setEditName(off.full_name);
                          setEditPhone(off.phone || "");
                          setEditIsActive(off.is_active);
                        }}
                        className="rounded border border-line bg-paper px-2.5 py-1 text-xs font-medium text-ink hover:bg-paper-dark"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteOfficer(off)}
                        className="rounded border border-risk/40 bg-risk/10 px-2.5 py-1 text-xs font-medium text-risk hover:bg-risk/20"
                      >
                        Deactivate
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Provision New Officer Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-paper p-6 shadow-xl">
            <h3 className="font-serif text-lg text-ink">Provision New Area Officer</h3>
            <p className="mt-1 text-xs text-ink-soft">
              Create an authenticated officer profile with assigned revenue jurisdiction.
            </p>

            <form onSubmit={handleCreateOfficer} className="mt-4 space-y-3 text-xs">
              <div>
                <label className="block font-medium text-ink">Full Officer Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Officer Rajesh Sharma"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-ink">Official Email</label>
                <input
                  type="email"
                  required
                  placeholder="e.g. rajesh.officer@bhuraksha.gov.in"
                  value={createEmail}
                  onChange={(e) => setCreateEmail(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-ink">Temporary Password</label>
                <input
                  type="password"
                  required
                  value={createPassword}
                  onChange={(e) => setCreatePassword(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 font-mono text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-ink">Contact Phone (Optional)</label>
                <input
                  type="text"
                  placeholder="+919876543210"
                  value={createPhone}
                  onChange={(e) => setCreatePhone(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-ink">Initial Dedicated Jurisdiction</label>
                <select
                  value={createAreaId}
                  onChange={(e) => setCreateAreaId(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                >
                  <option value="">-- No initial area --</option>
                  {areas.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.code})
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-6 flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded border border-line px-4 py-2 font-medium text-ink hover:bg-paper-dark"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="rounded bg-ink px-4 py-2 font-medium text-paper hover:bg-ink/90 disabled:opacity-50"
                >
                  {isCreating ? "Provisioning..." : "Create Area Officer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Officer Modal */}
      {editOfficer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-paper p-6 shadow-xl">
            <h3 className="font-serif text-lg text-ink">Edit Area Officer Profile</h3>
            <p className="mt-1 text-xs text-ink-soft">
              Update details for officer {editOfficer.email}.
            </p>

            <form onSubmit={handleUpdateOfficer} className="mt-4 space-y-3 text-xs">
              <div>
                <label className="block font-medium text-ink">Full Name</label>
                <input
                  type="text"
                  required
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div>
                <label className="block font-medium text-ink">Phone</label>
                <input
                  type="text"
                  value={editPhone}
                  onChange={(e) => setEditPhone(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                />
              </div>

              <div className="pt-2">
                <label className="flex items-center gap-2 cursor-pointer font-medium text-ink">
                  <input
                    type="checkbox"
                    checked={editIsActive}
                    onChange={(e) => setEditIsActive(e.target.checked)}
                    className="accent-verified h-4 w-4"
                  />
                  <span>Active Account Status</span>
                </label>
              </div>

              <div className="mt-6 flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditOfficer(null)}
                  className="rounded border border-line px-4 py-2 font-medium text-ink hover:bg-paper-dark"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdating}
                  className="rounded bg-ink px-4 py-2 font-medium text-paper hover:bg-ink/90 disabled:opacity-50"
                >
                  {isUpdating ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Area Modal */}
      {assignOfficerTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-md rounded-lg border border-line bg-paper p-6 shadow-xl">
            <h3 className="font-serif text-lg text-ink">
              Assign Dedicated Area to {assignOfficerTarget.full_name}
            </h3>
            <p className="mt-1 text-xs text-ink-soft">
              Select the administrative district this officer will have exclusive review jurisdiction over.
            </p>

            <div className="mt-4 space-y-3 text-xs">
              <div>
                <label className="block font-medium text-ink">Geographical Revenue Area</label>
                <select
                  value={selectedAssignAreaId}
                  onChange={(e) => setSelectedAssignAreaId(e.target.value)}
                  className="mt-1 w-full rounded border border-line bg-paper px-3 py-2 text-ink focus:border-brass focus:outline-none"
                >
                  {areas.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.code})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2 text-xs">
              <button
                type="button"
                onClick={() => setAssignOfficerTarget(null)}
                className="rounded border border-line px-4 py-2 font-medium text-ink hover:bg-paper-dark"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAssignArea}
                disabled={isAssigning}
                className="rounded bg-verified px-4 py-2 font-medium text-paper hover:opacity-90 disabled:opacity-50"
              >
                {isAssigning ? "Assigning..." : "Confirm Area Assignment"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="mt-10">
        <Link href="/queue" className="text-xs text-ink-soft underline underline-offset-2 hover:text-ink">
          ← Back to Global Verification Queue
        </Link>
      </div>
    </div>
  );
}
