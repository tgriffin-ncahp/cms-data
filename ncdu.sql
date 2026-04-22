

CREATE TABLE ncdu24 AS 
  SELECT 
    "Utilization Type" as payor, 
    state,
    NDC,
    "Labeler Code" as labaler,
    "Product Code" as product,
    "Package Size" as package_size,
    Year,
    Quarter,
    "Suppression Used" AS supression,
    "Product Name" AS product_name,
    "Units Reimbursed" AS units,
    "Number of Prescriptions" AS scripts,
    "Total Amount Reimbursed" AS total,
    "Medicaid Amount Reimbursed" AS medicaid,
    "Non Medicaid Amount Reimbursed" AS other
  FROM sdu_2024;:TEXT


SELECT 
  n.product_name, 
  printf('%,d',SUM(n.total)) AS total 
FROM ncdu25 as n
JOIN 


<F16>

sqlite> PRAGMA table_info(sdu_2025);
╭─────┬────────────────────────────────┬────────┬─────────┬────────────┬────╮
│ cid │              name              │  type  │ notnull │ dflt_value │ pk │
╞═════╪════════════════════════════════╪════════╪═════════╪════════════╪════╡
│   0 │ Utilization Type               │ TEXT   │       0 │            │  0 │
│   1 │ State                          │ TEXT   │       0 │            │  0 │
│   2 │ NDC                            │ TEXT   │       0 │            │  0 │
│   3 │ Labeler Code                   │ TEXT   │       0 │            │  0 │
│   4 │ Product Code                   │ TEXT   │       0 │            │  0 │
│   5 │ Package Size                   │ TEXT   │       0 │            │  0 │
│   6 │ Year                           │ BIGINT │       0 │            │  0 │
│   7 │ Quarter                        │ BIGINT │       0 │            │  0 │
│   8 │ Suppression Used               │ TEXT   │       0 │            │  0 │
│   9 │ Product Name                   │ TEXT   │       0 │            │  0 │
│  10 │ Units Reimbursed               │ FLOAT  │       0 │            │  0 │
│  11 │ Number of Prescriptions        │ FLOAT  │       0 │            │  0 │
│  12 │ Total Amount Reimbursed        │ FLOAT  │       0 │            │  0 │
│  13 │ Medicaid Amount Reimbursed     │ FLOAT  │       0 │            │  0 │
│  14 │ Non Medicaid Amount Reimbursed │ FLOAT  │       0 │            │  0 │
╰─────┴────────────────────────────────┴────────┴─────────┴────────────┴────╯



