SELECT "Product Name", printf('%,d', SUM("Product Name")) AS units, printf('%,d', SUM("Total Amount Reimbursed")),  FROM sdu_2025
GROUP BY "Product Name";

sqlite> .schema sdu_2025
CREATE TABLE sdu_2025 (
        "Utilization Type" TEXT,
        "State" TEXT,
        "NDC" TEXT,
        "Labeler Code" TEXT,
        "Product Code" TEXT,
        "Package Size" TEXT,
        "Year" BIGINT,
        "Quarter" BIGINT,
        "Suppression Used" TEXT,
        "Product Name" TEXT,
        "Units Reimbursed" FLOAT,
        "Number of Prescriptions" FLOAT,
        "Total Amount Reimbursed" FLOAT,
        "Medicaid Amount Reimbursed" FLOAT,
        "Non Medicaid Amount Reimbursed" FLOAT
);
CREATE INDEX idx_sdu2025_product ON sdu_2025("Product Name");
CREATE INDEX idx_sdu2025_ndc ON sdu_2025(NDC);
