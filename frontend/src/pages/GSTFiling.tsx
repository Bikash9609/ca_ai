import { useState, useEffect } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  Select,
  SelectItem,
  Button,
  Chip,
} from "@heroui/react";
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
        <div className="text-center text-default-500">
          Please select a client to view GST filing
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-foreground">GST Filing</h1>

      {/* Period Selection */}
      <Card classNames={{ base: "border border-default-200" }}>
        <CardHeader>
          <h2 className="text-lg font-semibold text-foreground">
            Select Period
          </h2>
        </CardHeader>
        <CardBody>
          <div className="flex gap-4">
            <Select
              label="Period"
              selectedKeys={selectedPeriod ? [selectedPeriod] : []}
              onSelectionChange={(keys) => {
                const selected = Array.from(keys)[0] as string;
                setSelectedPeriod(selected || "");
              }}
              placeholder="Select a period"
              className="flex-1"
            >
              {generatePeriods().map((period) => (
                <SelectItem key={period.value} value={period.value}>
                  {period.label}
                </SelectItem>
              ))}
            </Select>
            <Button color="primary">Financial Year View</Button>
          </div>
        </CardBody>
      </Card>

      {selectedPeriod && filingStatus && (
        <>
          {/* Filing Dashboard */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* GSTR-1 Status */}
            <Card classNames={{ base: "border border-default-200" }}>
              <CardHeader>
                <h3 className="text-lg font-semibold text-foreground">
                  GSTR-1 Status
                </h3>
              </CardHeader>
              <CardBody className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-foreground">Status:</span>
                  <Chip
                    color={
                      filingStatus.gstr1_status === "filed"
                        ? "success"
                        : filingStatus.gstr1_status === "draft"
                        ? "warning"
                        : "default"
                    }
                  >
                    {filingStatus.gstr1_status.replace("_", " ").toUpperCase()}
                  </Chip>
                </div>
                <Button color="primary" className="w-full">
                  {filingStatus.gstr1_status === "filed"
                    ? "View Filed Return"
                    : "File GSTR-1"}
                </Button>
              </CardBody>
            </Card>

            {/* GSTR-3B Status */}
            <Card classNames={{ base: "border border-default-200" }}>
              <CardHeader>
                <h3 className="text-lg font-semibold text-foreground">
                  GSTR-3B Status
                </h3>
              </CardHeader>
              <CardBody className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-foreground">Status:</span>
                  <Chip
                    color={
                      filingStatus.gstr3b_status === "filed"
                        ? "success"
                        : filingStatus.gstr3b_status === "draft"
                        ? "warning"
                        : "default"
                    }
                  >
                    {filingStatus.gstr3b_status.replace("_", " ").toUpperCase()}
                  </Chip>
                </div>
                <Button color="primary" className="w-full">
                  {filingStatus.gstr3b_status === "filed"
                    ? "View Filed Return"
                    : "File GSTR-3B"}
                </Button>
              </CardBody>
            </Card>
          </div>

          {/* ITC Summary */}
          <Card classNames={{ base: "border border-default-200" }}>
            <CardHeader>
              <h3 className="text-lg font-semibold text-foreground">
                ITC Summary
              </h3>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-sm text-default-500">Eligible ITC</div>
                  <div className="text-2xl font-bold text-success">
                    ₹{filingStatus.itc_summary.eligible.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-default-500">Blocked ITC</div>
                  <div className="text-2xl font-bold text-danger">
                    ₹{filingStatus.itc_summary.blocked.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-default-500">Total ITC</div>
                  <div className="text-2xl font-bold text-foreground">
                    ₹{filingStatus.itc_summary.total.toLocaleString()}
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Reconciliation Status */}
          <Card classNames={{ base: "border border-default-200" }}>
            <CardHeader>
              <h3 className="text-lg font-semibold text-foreground">
                Reconciliation Status
              </h3>
            </CardHeader>
            <CardBody>
              <div className="flex items-center justify-between">
                <Chip
                  color={
                    filingStatus.reconciliation_status === "completed"
                      ? "success"
                      : "warning"
                  }
                >
                  {filingStatus.reconciliation_status.toUpperCase()}
                </Chip>
                <Button color="primary">View Reconciliation</Button>
              </div>
            </CardBody>
          </Card>

          {/* Draft Review */}
          <Card classNames={{ base: "border border-default-200" }}>
            <CardHeader>
              <h3 className="text-lg font-semibold text-foreground">
                Draft Review
              </h3>
            </CardHeader>
            <CardBody>
              <div className="space-y-4">
                <Card classNames={{ base: "border border-default-200" }}>
                  <CardBody>
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-medium text-foreground">
                        GSTR-3B Draft
                      </span>
                      <span className="text-sm text-default-500">
                        Last updated: Today
                      </span>
                    </div>
                    <p className="text-sm text-default-600 mb-4">
                      Review the draft before filing
                    </p>
                    <div className="flex gap-2">
                      <Button color="primary">Review Draft</Button>
                      <Button variant="bordered">Export</Button>
                      <Button variant="bordered">Approve</Button>
                    </div>
                  </CardBody>
                </Card>
              </div>
            </CardBody>
          </Card>
        </>
      )}

      {!selectedPeriod && (
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody>
            <div className="text-center text-default-500">
              Select a period to view filing status
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
