"use client";
import { useState, useEffect, useRef } from "react";
import Papa from "papaparse";

interface AuditResult {
  id: number;
  companyName: string;
  url?: string;
  pdf_url?: string;
  excel_url?: string;
  timestamp?: number;
  status?: "processing" | "success" | "error";
  error?: string;
}

const COLORS = {
  primary: "#0027E3",
  aqua: "#00FFCC",
  purple: "#7000FF",
  magenta: "#F605FE",
  navy: "#06103A",
  ink: "#141C3A",
  slate: "#3D4A6B",
  white: "#FFFFFF",
  softblue: "#D5E8FF",
  lavender: "#E3CAFF",
  mint: "#CCFFEA",
  pink: "#FDCBFF",
};

export default function Home() {
  const [url, setUrl] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"single" | "batch">("single");
  const [history, setHistory] = useState<AuditResult[]>([]);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // 🚨 INI KUNCI DEPLOYMENT-NYA 🚨
  // Kalau di server, dia pakai URL Render. Kalau di laptop, dia pakai localhost.
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    const saved = localStorage.getItem("audit_history");
    if (saved) setHistory(JSON.parse(saved));
  }, []);

  const showNotification = (type: "success" | "error", message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  const isValidUrl = (str: string) => {
    try {
      new URL(str);
      return true;
    } catch {
      return false;
    }
  };

  const runAudit = async (name: string, targetUrl: string) => {
    if (!name.trim()) return showNotification("error", "Company name cannot be empty");
    if (!targetUrl.trim()) return showNotification("error", "Website URL cannot be empty");
    if (!isValidUrl(targetUrl)) return showNotification("error", "Invalid URL format (use https://...)");

    setLoading(true);

    const newEntry: AuditResult = {
      id: Date.now(),
      companyName: name,
      url: targetUrl,
      timestamp: Date.now(),
      status: "processing",
    };

    setHistory(prev => {
      const updated = [newEntry, ...prev];
      localStorage.setItem("audit_history", JSON.stringify(updated));
      return updated;
    });

    try {
      // 🚨 URL DINAMIS DI SINI 🚨
      const resp = await fetch(`${API_BASE_URL}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: targetUrl, company_name: name }),
      });

      const data = await resp.json();

      if (!resp.ok) throw new Error(data?.detail || "Audit failed");

      const completed: AuditResult = {
        ...newEntry,
        ...data.data,
        status: "success",
      };

      setHistory(prev => {
        const updated = prev.map(it => (it.id === newEntry.id ? completed : it));
        localStorage.setItem("audit_history", JSON.stringify(updated));
        return updated;
      });

      showNotification("success", `✓ Audit successful for ${name}`);
      setCompanyName("");
      setUrl("");
    } catch (err: any) {
      const message = err?.message || "An error occurred during audit";
      setHistory(prev => {
        const updated = prev.map(it => it.id === newEntry.id ? { ...it, status: "error", error: message } : it);
        localStorage.setItem("audit_history", JSON.stringify(updated));
        return updated;
      });
      showNotification("error", message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results: any) => {
        // Filter baris yang valid
        const rows = results.data.filter((r: any) => r.name && r.url);
        if (rows.length === 0) return showNotification("error", "CSV must have 'name' and 'url' columns with valid data");

        setBatchProgress({ current: 0, total: rows.length });
        setLoading(true);

        for (let i = 0; i < rows.length; i++) {
          const row = rows[i];
          
          // Auto-Sanitize: Bersihkan tanda kutip (") atau spasi nyasar dari CSV
          const cleanName = row.name.trim().replace(/['"]/g, '');
          const cleanUrl = row.url.trim().replace(/['"]/g, '');

          await runAudit(cleanName, cleanUrl);
          setBatchProgress({ current: i + 1, total: rows.length });

          // Smart Throttling: Beri jeda 10 detik ke server Render sebelum lanjut ke klien berikutnya (kecuali ini klien terakhir)
          if (i < rows.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 10000));
          }
        }

        setLoading(false);
        setBatchProgress({ current: 0, total: 0 });
        if (fileInputRef.current) fileInputRef.current.value = "";
        showNotification("success", `✓ Batch audit complete! ${rows.length} websites processed`);
      },
      error: () => showNotification("error", "Invalid CSV format"),
    });
  };

  const deleteAudit = (id: number) => {
    setHistory(prev => {
      const updated = prev.filter(i => i.id !== id);
      localStorage.setItem("audit_history", JSON.stringify(updated));
      return updated;
    });
    showNotification("success", "Audit removed");
  };

  const clearHistory = () => {
    if (!confirm("Clear all audit history?")) return;
    setHistory([]);
    localStorage.removeItem("audit_history");
    showNotification("success", "History cleared");
  };

  const formatDate = (ts?: number) => {
    if (!ts) return "";
    return new Date(ts).toLocaleString();
  };

  const getStatusBadge = (status?: string) => {
    if (status === "success") return <span style={{ background: COLORS.mint, color: "#0A7A50", padding: "6px 10px", borderRadius: 999, fontWeight: 700, fontSize: 12 }}>✓ Complete</span>;
    if (status === "error") return <span style={{ background: "#FFE8EA", color: "#C0001A", padding: "6px 10px", borderRadius: 999, fontWeight: 700, fontSize: 12 }}>✗ Failed</span>;
    if (status === "processing") return <span style={{ background: COLORS.softblue, color: COLORS.primary, padding: "6px 10px", borderRadius: 999, fontWeight: 700, fontSize: 12 }}>⏳ Processing</span>;
    return null;
  };

  return (
    <main style={{ background: "#F7F9FE", minHeight: "100vh" }}>
      <div style={{ background: COLORS.white, borderBottom: "1px solid #E4E9F5" }}>
        <div style={{ maxWidth: 1280, margin: "0 auto", padding: "16px 24px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.purple})`, padding: "8px 16px", borderRadius: 8 }}>
              <span style={{ color: "white", fontWeight: 700, fontSize: 20 }}>BR</span>
            </div>
            <div>
              <h1 style={{ fontSize: 32, fontWeight: 900, color: COLORS.ink, margin: 0 }}>SEO Audit Engine</h1>
              <p style={{ color: COLORS.slate, fontSize: 12, margin: "4px 0 0 0" }}>Powered by BlueRock Digital</p>
            </div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "40px 24px" }}>
        <p style={{ color: COLORS.slate, fontSize: 16, maxWidth: 600, marginBottom: 32, lineHeight: 1.6 }}>
          Comprehensive website audit and SEO opportunity review. Get detailed reports in minutes and discover actionable insights to improve your digital presence.
        </p>

        {notification && (
          <div style={{ marginBottom: 24, padding: 16, borderRadius: 12, fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 12, border: `1px solid ${notification.type === "success" ? COLORS.aqua : "#F0D0D5"}`, background: notification.type === "success" ? COLORS.mint + "40" : "#FFE8EA", color: notification.type === "success" ? "#0A7A50" : "#C0001A" }}>
            <span style={{ fontSize: 18 }}>{notification.type === "success" ? "✓" : "✕"}</span>
            <span>{notification.message}</span>
          </div>
        )}

        <div style={{ background: COLORS.white, border: "1px solid #E4E9F5", borderRadius: 16, overflow: "hidden", marginBottom: 40, boxShadow: "0 4px 20px rgba(0, 39, 227, 0.08)" }}>
          <div style={{ display: "flex", borderBottom: "1px solid #E4E9F5", background: "#F7F9FE" }}>
            <button onClick={() => setActiveTab("single")} style={{ flex: 1, padding: "16px 24px", fontWeight: 700, fontSize: 16, border: "none", background: activeTab === "single" ? COLORS.primary : "transparent", color: activeTab === "single" ? "white" : COLORS.slate, cursor: "pointer" }}>🔗 Single Audit</button>
            <button onClick={() => setActiveTab("batch")} style={{ flex: 1, padding: "16px 24px", fontWeight: 700, fontSize: 16, border: "none", borderLeft: "1px solid #E4E9F5", background: activeTab === "batch" ? COLORS.purple : "transparent", color: activeTab === "batch" ? "white" : COLORS.slate, cursor: "pointer" }}>📋 Batch Upload</button>
          </div>

          <div style={{ padding: 32 }}>
            {activeTab === "single" ? (
              <form onSubmit={(e) => { e.preventDefault(); runAudit(companyName, url); }} style={{ maxWidth: 500 }}>
                <div style={{ marginBottom: 20 }}>
                  <label style={{ display: "block", fontWeight: 700, fontSize: 14, marginBottom: 8, color: COLORS.ink }}>Company Name</label>
                  <input placeholder="e.g., Blue Rock Interactive" value={companyName} onChange={e => setCompanyName(e.target.value)} disabled={loading} style={{ width: "100%", padding: "12px 16px", border: "1px solid #E4E9F5", borderRadius: 8, fontSize: 14, color: COLORS.ink, background: COLORS.white, opacity: loading ? 0.6 : 1 }} />
                </div>
                <div style={{ marginBottom: 24 }}>
                  <label style={{ display: "block", fontWeight: 700, fontSize: 14, marginBottom: 8, color: COLORS.ink }}>Website URL</label>
                  <input placeholder="e.g., https://example.com" value={url} onChange={e => setUrl(e.target.value)} disabled={loading} style={{ width: "100%", padding: "12px 16px", border: "1px solid #E4E9F5", borderRadius: 8, fontSize: 14, color: COLORS.ink, background: COLORS.white, opacity: loading ? 0.6 : 1 }} />
                </div>
                <button type="submit" disabled={loading} style={{ width: "100%", padding: "12px 24px", background: `linear-gradient(135deg, ${COLORS.primary}, #003CC0)`, color: "white", fontWeight: 700, fontSize: 16, border: "none", borderRadius: 8, cursor: loading ? "not-allowed" : "pointer" }}>{loading ? "⏳ Processing..." : "🚀 Start Audit"}</button>
              </form>
            ) : (
              <div style={{ maxWidth: 600 }}>
                <div style={{ marginBottom: 20, padding: 16, background: "#F7F9FE", border: "1px solid #E4E9F5", borderRadius: 8 }}>
                  <p style={{ fontWeight: 600, fontSize: 14, marginBottom: 12, color: COLORS.ink }}>📋 CSV Format Required:</p>
                  <pre style={{ fontSize: 12, overflow: "auto", padding: 12, background: COLORS.white, border: "1px solid #E4E9F5", borderRadius: 6, color: COLORS.slate, fontFamily: "monospace", margin: 0 }}>{`name,url\nBlue Rock,https://example.com\nDigital Agency,https://example2.com`}</pre>
                </div>

                <div style={{ marginBottom: 20 }}>
                  <label style={{ display: "block", fontWeight: 700, fontSize: 14, marginBottom: 8, color: COLORS.ink }}>Upload CSV File</label>
                  <input type="file" accept=".csv" ref={fileInputRef} onChange={handleFileUpload} disabled={loading} style={{ width: "100%", padding: "12px 16px", border: "1px solid #E4E9F5", borderRadius: 8, fontSize: 14, color: COLORS.slate, background: COLORS.white, opacity: loading ? 0.6 : 1, cursor: "pointer" }} />
                  <p style={{ fontSize: 12, color: COLORS.slate, marginTop: 8 }}>Maximum 50 websites per batch. Processing may take several minutes.</p>
                </div>

                {batchProgress.total > 0 && (
                  <div style={{ padding: 16, background: "#F7F9FE", border: "1px solid #E4E9F5", borderRadius: 8 }}>
                    <p style={{ fontWeight: 600, fontSize: 14, margin: 0, color: COLORS.ink }}>Progress: {batchProgress.current}/{batchProgress.total}</p>
                    <div style={{ width: "100%", height: 12, background: "#F0F5FF", borderRadius: 6, overflow: "hidden", border: "1px solid #E4E9F5", marginTop: 8 }}>
                      <div style={{ height: "100%", background: `linear-gradient(90deg, ${COLORS.primary}, ${COLORS.aqua})`, width: `${(batchProgress.current / batchProgress.total) * 100}%`, transition: "width 0.3s ease" }} />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div style={{ marginTop: 40 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
            <h2 style={{ fontSize: 24, fontWeight: 700, color: COLORS.ink, display: "flex", alignItems: "center", gap: 12, margin: 0 }}>📊 Audit History {history.length > 0 && <span style={{ fontSize: 14, fontWeight: 700, padding: "4px 12px", borderRadius: 20, background: COLORS.softblue, color: COLORS.primary, marginLeft: 12 }}>{history.length}</span>}</h2>
            {history.length > 0 && (
              <button onClick={clearHistory} style={{ fontSize: 14, fontWeight: 700, padding: "8px 16px", borderRadius: 8, background: "#FFE8EA", color: "#C0001A", border: "none", cursor: "pointer" }}>🗑️ Clear All</button>
            )}
          </div>

          {history.length === 0 ? (
            <div style={{ padding: "48px 24px", textAlign: "center", border: "1px solid #E4E9F5", borderRadius: 16, background: COLORS.white }}>
              <p style={{ fontSize: 48, margin: 0 }}>📭</p>
              <p style={{ color: COLORS.slate, fontSize: 16, marginTop: 12 }}>No audits yet. Start your first website audit to get comprehensive SEO insights.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gap: 16 }}>
              {history.map(item => (
                <div key={item.id} style={{ background: COLORS.white, border: `2px solid ${item.status === "success" ? COLORS.mint : item.status === "error" ? "#FFE8EA" : COLORS.softblue}`, borderRadius: 12, padding: 20 }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: COLORS.ink }}>{item.companyName}</h3>
                      {getStatusBadge(item.status)}
                    </div>
                    <p style={{ margin: 0, color: COLORS.slate }}>{item.url || "URL not available"}</p>
                    <p style={{ margin: 0, color: COLORS.slate, fontSize: 12 }}>{formatDate(item.timestamp)}</p>

                    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                      {item.status === "success" && (
                        <>
                          {/* 🚨 URL DINAMIS DI SINI JUGA 🚨 */}
                          <a href={`${API_BASE_URL}${item.pdf_url}`} target="_blank" rel="noreferrer" style={{ padding: "8px 16px", background: "#E8405A", color: "white", borderRadius: 6, textDecoration: "none", fontWeight: 700 }}>📄 PDF Report</a>
                          <a href={`${API_BASE_URL}${item.excel_url}`} target="_blank" rel="noreferrer" style={{ padding: "8px 16px", background: "#22C57A", color: "white", borderRadius: 6, textDecoration: "none", fontWeight: 700 }}>📊 Data Export</a>
                        </>
                      )}
                      <button onClick={() => deleteAudit(item.id)} style={{ padding: "8px 12px", background: COLORS.softblue, color: COLORS.primary, borderRadius: 6, border: "none", fontWeight: 700 }}>🗑️ Delete</button>
                    </div>

                    {item.error && <p style={{ color: "#C0001A", marginTop: 8 }}>{item.error}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginTop: 64, paddingTop: 32, borderTop: "1px solid #E4E9F5" }}>
          <p style={{ color: COLORS.slate, fontSize: 12, textAlign: "center", opacity: 0.75, margin: 0 }}>© 2026 BlueRock Digital. All rights reserved. | Website Opportunity Review & SEO Audit Engine</p>
        </div>
      </div>
    </main>
  );
}