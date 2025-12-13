import { useState, useEffect } from "react";
import { useWorkspace } from "../hooks/useWorkspace";

interface FilingStatus {
  period: string;
  gstr1_status: "not_filed" | "draft" | "filed";
  gstr3b_status: "not_filed" | "draft" | "filed";
  itc_summary: {
    eligible: number;
    blocked: number;
    total: number;
  };
  reconciliation_status: "pending" | "completed";
}

export default function GSTFiling() {
  const { currentClient } = useWorkspace();
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");
  const [filingStatus, setFilingStatus] = useState<FilingStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (currentClient && selectedPeriod) {
      loadFilingStatus();
    }
  }, [currentClient, selectedPeriod]);

  const loadFilingStatus = async () => {
    if (!currentClient || !selectedPeriod) return;
    setLoading(true);
    try {
      // TODO: Fetch from API
      setFilingStatus({
        period: selectedPeriod,
        gstr1_status: "draft",
        gstr3b_status: "not_filed",
        itc_summary: {
          eligible: 0,
          blocked: 0,
          total: 0,
        },
        reconciliation_status: "pending",
      });
    } catch (error) {
      console.error("Failed to load filing status:", error);
    } finally {
      setLoading(false);
    }
  };

  const generatePeriods = () => {
    const periods = [];
    const currentDate = new Date();
    for (let i = 0; i < 12; i++) {
      const date = new Date(
        currentDate.getFullYear(),
        currentDate.getMonth() - i,
        1
      );
      const period = `${date.getFullYear()}-${String(
        date.getMonth() + 1
      ).padStart(2, "0")}`;
      periods.push({
        value: period,
        label: date.toLocaleDateString("en-US", {
          month: "long",
          year: "numeric",
        }),
      });
    }
    return periods;
  };

  if (!currentClient) {
    return (
      <div className="p-6">
        <div className="text-center text-gray-500">
          Please select a client to view GST filing
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">GST Filing</h1>

      {/* Period Selection */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Select Period</h2>
        <div className="flex gap-4">
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
            className="px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select a period</option>
            {generatePeriods().map((period) => (
              <option key={period.value} value={period.value}>
                {period.label}
              </option>
            ))}
          </select>
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Financial Year View
          </button>
        </div>
      </div>

      {selectedPeriod && filingStatus && (
        <>
          {/* Filing Dashboard */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* GSTR-1 Status */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">GSTR-1 Status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span>Status:</span>
                  <span
                    className={`px-3 py-1 rounded text-sm ${
                      filingStatus.gstr1_status === "filed"
                        ? "bg-green-100 text-green-800"
                        : filingStatus.gstr1_status === "draft"
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {filingStatus.gstr1_status.replace("_", " ").toUpperCase()}
                  </span>
                </div>
                <button className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                  {filingStatus.gstr1_status === "filed"
                    ? "View Filed Return"
                    : "File GSTR-1"}
                </button>
              </div>
            </div>

            {/* GSTR-3B Status */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">GSTR-3B Status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span>Status:</span>
                  <span
                    className={`px-3 py-1 rounded text-sm ${
                      filingStatus.gstr3b_status === "filed"
                        ? "bg-green-100 text-green-800"
                        : filingStatus.gstr3b_status === "draft"
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {filingStatus.gstr3b_status.replace("_", " ").toUpperCase()}
                  </span>
                </div>
                <button className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                  {filingStatus.gstr3b_status === "filed"
                    ? "View Filed Return"
                    : "File GSTR-3B"}
                </button>
              </div>
            </div>
          </div>

          {/* ITC Summary */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">ITC Summary</h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-sm text-gray-500">Eligible ITC</div>
                <div className="text-2xl font-bold text-green-600">
                  ₹{filingStatus.itc_summary.eligible.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Blocked ITC</div>
                <div className="text-2xl font-bold text-red-600">
                  ₹{filingStatus.itc_summary.blocked.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Total ITC</div>
                <div className="text-2xl font-bold">
                  ₹{filingStatus.itc_summary.total.toLocaleString()}
                </div>
              </div>
            </div>
          </div>

          {/* Reconciliation Status */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">
              Reconciliation Status
            </h3>
            <div className="flex items-center justify-between">
              <span
                className={`px-3 py-1 rounded ${
                  filingStatus.reconciliation_status === "completed"
                    ? "bg-green-100 text-green-800"
                    : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {filingStatus.reconciliation_status.toUpperCase()}
              </span>
              <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                View Reconciliation
              </button>
            </div>
          </div>

          {/* Draft Review */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Draft Review</h3>
            <div className="space-y-4">
              <div className="border rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-medium">GSTR-3B Draft</span>
                  <span className="text-sm text-gray-500">
                    Last updated: Today
                  </span>
                </div>
                <p className="text-sm text-gray-600 mb-4">
                  Review the draft before filing
                </p>
                <div className="flex gap-2">
                  <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                    Review Draft
                  </button>
                  <button className="px-4 py-2 border rounded hover:bg-gray-50">
                    Export
                  </button>
                  <button className="px-4 py-2 border rounded hover:bg-gray-50">
                    Approve
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {!selectedPeriod && (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
          Select a period to view filing status
        </div>
      )}
    </div>
  );
}
