# Frappe OKR Management

A Frappe v15 / ERPNext custom app for managing Objectives and Key Results across planning, execution, review, and executive reporting.

## Overview

`okr_management` helps an organization define OKR cycles, create objectives, track measurable key results, capture check-ins, review progress, and present management-level analytics in a clean ERP-style workspace.

## Features

- OKR cycle, objective, key result, check-in, review, and action item DocTypes
- Automatic progress and confidence rollups
- Employee-friendly check-in workflow
- Manager review workflow
- Executive dashboard with number cards and charts
- Executive Attention and rule-based OKR health insights
- Hierarchy view for Cycle → Objective → Key Result → Action Item
- Reports for summaries, at-risk OKRs, employee progress, health insights, cycle reviews, and action items
- Realistic demo data generator for CTO/client demos
- Role-based visibility for executives, department heads, managers, and employees
- ERPNext-style workspace navigation

## Requirements

- Frappe Framework v15
- ERPNext v15
- Bench environment

## Installation

From your bench folder:

```bash
bench get-app https://github.com/utsavmodi777-f1/frappe-okr-management.git
bench --site your-site.local install-app okr_management
bench --site your-site.local migrate
bench build --app okr_management
bench --site your-site.local clear-cache
bench restart
```

## Demo Data

Create demo OKR data:

```bash
bench --site your-site.local execute okr_management.demo_data.create_demo_data
```

Remove only demo records created by the generator:

```bash
bench --site your-site.local execute okr_management.demo_data.clear_demo_data
```

## Demo Flow

1. Open `/app/okr-management`.
2. Review the dashboard summary cards and analytics charts.
3. Go to Planning and create or inspect OKR Cycles and Objectives.
4. Go to Execution and review Key Results, Action Items, and Check-ins.
5. Go to Performance and inspect Objective Reviews.
6. Go to Analytics for Executive Attention, Health Insights, and management reports.
7. Use the Hierarchy Tree from Planning for Cycle → Objective → Key Result → Action Item navigation.

## Workspace Structure

```text
OKR Management
├── Dashboard
├── Planning
├── Execution
├── Performance
├── Analytics
└── Administration
```

## Development

This app follows standard Frappe app structure. Avoid committing generated files such as `__pycache__`, `.pyc`, `node_modules`, bench `sites`, logs, private keys, or environment files.

## License

MIT
