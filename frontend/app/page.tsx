"use client"

import React, { useEffect, useState, useRef } from "react"
import {
  Leaf,
  Store,
  ChevronDown,
  Bell,
  ShieldCheck,
  Eye,
  CloudUpload,
  PackageCheck,
  TriangleAlert,
  CircleDollarSign,
  TrendingUp,
  Camera,
  ScanLine,
  Activity,
  ArrowUpRight,
  Sparkles,
  Tag,
  Zap,
  LockKeyhole,
  ChefHat,
  CheckCircle2,
  SlidersHorizontal,
  Smartphone,
  Columns2,
} from "lucide-react"

const API_BASE = "http://127.0.0.1:8000"

interface SlmContent {
  headline: string
  discount_badge?: string
  recipe_title: string
  ingredients: string[]
  instructions: string[]
}

interface InventoryItem {
  item_id: string
  name: string
  category: string
  is_perishable: boolean
  tags: string[]
  cost_price: number
  original_price: number
  min_allowed_price: number
  stock_count: number
  shelf_capacity: number
  current_stock_pct: number
  freshness_score: number
  freshness_status: "Peak" | "Overripe" | "Spoiled" | "Shelf_Stable"
  cv_confidence?: number
  recommended_action: string
  recommended_price: number | null
  bundle_partner_id?: string | null
  merchandising_note?: string
  approval_status: "PENDING" | "APPROVED" | "REJECTED"
  slm_generated: SlmContent | null
}

const FALLBACK_INVENTORY: InventoryItem[] = [
  {
    item_id: "prod_101",
    name: "Cavendish Bananas (1 Dozen)",
    category: "Produce",
    is_perishable: true,
    tags: ["tag_baking", "tag_smoothie", "tag_breakfast"],
    cost_price: 30.0,
    original_price: 60.0,
    min_allowed_price: 31.5,
    stock_count: 42,
    shelf_capacity: 50,
    current_stock_pct: 0.84,
    freshness_score: 0.35,
    freshness_status: "Overripe",
    cv_confidence: 0.94,
    recommended_action: "BUNDLE_AND_MARKDOWN",
    recommended_price: 40.0,
    bundle_partner_id: "prod_102",
    merchandising_note:
      "Pair Overripe Bananas (33% markdown) with overstocked Whole Wheat Flour (92% stock) on end-cap display for Banana Bread.",
    approval_status: "APPROVED",
    slm_generated: {
      headline: "Bake Tonight: Zero-Waste Banana Bread Bundle!",
      discount_badge: "Save ₹20 + Flour Combo",
      recipe_title: "3-Ingredient Caramelized Banana Bread",
      ingredients: ["3 Overripe Bananas", "2 Cups Whole Wheat Flour", "1/2 Cup Jaggery or Honey"],
      instructions: [
        "Mash the sweet overripe bananas in a bowl until smooth.",
        "Fold in whole wheat flour, sweetener, and a pinch of cinnamon.",
        "Bake at 180°C for 35 minutes until golden brown.",
      ],
    },
  },
  {
    item_id: "prod_102",
    name: "Whole Wheat Baking Flour (1 kg)",
    category: "Pantry_Anchor",
    is_perishable: false,
    tags: ["tag_baking"],
    cost_price: 38.0,
    original_price: 55.0,
    min_allowed_price: 39.9,
    stock_count: 46,
    shelf_capacity: 50,
    current_stock_pct: 0.92,
    freshness_score: 1.0,
    freshness_status: "Shelf_Stable",
    cv_confidence: 0.98,
    recommended_action: "CROSS_MERCH_FULL_PRICE",
    recommended_price: 55.0,
    bundle_partner_id: "prod_101",
    merchandising_note:
      "Overstocked at 92%. Protect margin—do not markdown alone. Cross-merchandise next to Overripe Bananas under 'Baking' tag.",
    approval_status: "APPROVED",
    slm_generated: null,
  },
  {
    item_id: "prod_103",
    name: "Hass Avocados (Pack of 2)",
    category: "Produce",
    is_perishable: true,
    tags: ["tag_mexican", "tag_breakfast"],
    cost_price: 120.0,
    original_price: 250.0,
    min_allowed_price: 126.0,
    stock_count: 14,
    shelf_capacity: 15,
    current_stock_pct: 0.9333,
    freshness_score: 0.42,
    freshness_status: "Overripe",
    cv_confidence: 0.91,
    recommended_action: "MARKDOWN",
    recommended_price: 150.0,
    bundle_partner_id: "prod_104",
    merchandising_note:
      "Softening rapidly with 93% stock remaining. Apply 40% markdown (above ₹126.00 margin floor) and cross-place with Greek Yogurt.",
    approval_status: "PENDING",
    slm_generated: {
      headline: "Flash Sale: Ready-to-Eat Guacamole Night!",
      discount_badge: "40% OFF Today Only",
      recipe_title: "10-Minute Creamy Avocado Dip",
      ingredients: ["2 Ripe Avocados", "1 Lime", "Salt, Pepper & Coriander"],
      instructions: [
        "Scoop ripe avocados into a bowl and mash with a fork.",
        "Squeeze fresh lime juice and fold in chopped coriander, salt, and pepper.",
      ],
    },
  },
  {
    item_id: "prod_104",
    name: "Greek Yogurt Tub (400g)",
    category: "Dairy",
    is_perishable: true,
    tags: ["tag_smoothie", "tag_breakfast", "tag_mexican"],
    cost_price: 65.0,
    original_price: 110.0,
    min_allowed_price: 68.25,
    stock_count: 28,
    shelf_capacity: 30,
    current_stock_pct: 0.9333,
    freshness_score: 0.88,
    freshness_status: "Peak",
    cv_confidence: 0.96,
    recommended_action: "CROSS_MERCH_FULL_PRICE",
    recommended_price: 110.0,
    bundle_partner_id: "prod_101",
    merchandising_note:
      "Fresh (Peak) but Overstocked (93%). Keep full price to protect margin; bundle with Bananas for a 'Morning Smoothie Bowl' feature.",
    approval_status: "PENDING",
    slm_generated: {
      headline: "Power Breakfast: Greek Yogurt & Banana Smoothie Pack",
      discount_badge: "Combo Feature",
      recipe_title: "2-Minute High-Protein Banana Smoothie",
      ingredients: ["1 Cup Greek Yogurt", "1 Ripe Banana", "Splash of Milk"],
      instructions: [
        "Add Greek yogurt and sliced banana to a blender.",
        "Blend on high for 60 seconds until thick and creamy.",
      ],
    },
  },
  {
    item_id: "prod_105",
    name: "Roma Tomatoes (1 kg)",
    category: "Produce",
    is_perishable: true,
    tags: ["tag_pasta", "tag_mexican"],
    cost_price: 25.0,
    original_price: 50.0,
    min_allowed_price: 26.25,
    stock_count: 3,
    shelf_capacity: 40,
    current_stock_pct: 0.075,
    freshness_score: 0.92,
    freshness_status: "Peak",
    cv_confidence: 0.95,
    recommended_action: "REPLENISH_STOCK",
    recommended_price: 50.0,
    bundle_partner_id: null,
    merchandising_note:
      "Critical Low Stock (7.5% bin capacity). Peak freshness—retain full price and alert staff for immediate backroom replenishment.",
    approval_status: "PENDING",
    slm_generated: null,
  },
  {
    item_id: "prod_106",
    name: "Fresh Strawberries Box (250g)",
    category: "Produce",
    is_perishable: true,
    tags: ["tag_smoothie", "tag_breakfast"],
    cost_price: 90.0,
    original_price: 180.0,
    min_allowed_price: 94.5,
    stock_count: 6,
    shelf_capacity: 20,
    current_stock_pct: 0.3,
    freshness_score: 0.12,
    freshness_status: "Spoiled",
    cv_confidence: 0.89,
    recommended_action: "REMOVE_FROM_SHELF",
    recommended_price: null,
    bundle_partner_id: null,
    merchandising_note:
      "SAFETY GUARDRAIL TRIGGERED: Visible mold/spoilage detected (score 0.12). Markdown blocked. Alert floor staff to remove immediately.",
    approval_status: "APPROVED",
    slm_generated: null,
  },
]

// Helper functions fixing all formatting bugs
const money = (value: number | null | undefined) =>
  value != null && value > 0 ? `₹${Number(value).toFixed(2)}` : "BLOCKED"

const formatPct = (ratio: number) => {
  const val = ratio <= 1 ? ratio * 100 : ratio
  return `${Math.round(val)}%`
}

const cleanLabel = (raw: string) => raw.replace(/_/g, " ")

export default function Page() {
  const [items, setItems] = useState<InventoryItem[]>(FALLBACK_INVENTORY)
  const [viewMode, setViewMode] = useState<"manager" | "customer" | "split">("split")
  const [selectedItemId, setSelectedItemId] = useState<string>("prod_103")
  const [customPrice, setCustomPrice] = useState<number>(150.0)
  const [isScanning, setIsScanning] = useState<boolean>(false)
  const [scanResultBanner, setScanResultBanner] = useState<string | null>(null)
  const [toastMsg, setToastMsg] = useState<string | null>(null)
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL")
  const [expandedRecipeId, setExpandedRecipeId] = useState<string | null>("prod_101")
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setTimeout(() => setToastMsg(null), 3500)
  }

  // Fetch live inventory from FastAPI
  const fetchInventory = async () => {
    try {
      const res = await fetch(`${API_BASE}/get-recommendations`)
      if (res.ok) {
        const data = await res.json()
        if (data.inventory && data.inventory.length > 0) {
          setItems(data.inventory)
        }
      }
    } catch {
      // Uses fallback seamlessly if backend is restarting
    }
  }

  useEffect(() => {
    fetchInventory()
  }, [])

  const selectedItem =
    items.find((i) => i.item_id === selectedItemId) ||
    items.find((i) => i.freshness_status === "Overripe") ||
    items[0]

  const partnerItem = selectedItem?.bundle_partner_id
    ? items.find((i) => i.item_id === selectedItem.bundle_partner_id)
    : items.find((i) => i.category === "Pantry_Anchor")

  useEffect(() => {
    if (selectedItem) {
      const safeDefault =
        selectedItem.recommended_price && selectedItem.recommended_price > 0
          ? selectedItem.recommended_price
          : selectedItem.original_price
      setCustomPrice(safeDefault)
    }
  }, [selectedItemId])

  // Approve item via FastAPI + update live UI state
  const handleApprove = async (item: InventoryItem, priceOverride?: number) => {
    if (item.freshness_status === "Spoiled") {
      showToast("Safety Guardrail: Spoiled items are locked to REMOVE FROM SHELF.")
      return
    }
    const finalPrice = priceOverride ?? item.recommended_price ?? item.original_price
    if (finalPrice < item.min_allowed_price) {
      showToast(`Guardrail Violation: Cannot price below ₹${item.min_allowed_price.toFixed(2)} (Cost + 5%)`)
      return
    }

    // Optimistic update
    setItems((prev) =>
      prev.map((it) =>
        it.item_id === item.item_id
          ? { ...it, approval_status: "APPROVED", recommended_price: finalPrice }
          : it
      )
    )
    setExpandedRecipeId(item.item_id)
    showToast(`Approved "${item.name}" at ₹${finalPrice.toFixed(2)} → Pushed to Customer Loyalty App!`)

    try {
      await fetch(`${API_BASE}/approve-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_id: item.item_id,
          approval_status: "APPROVED",
          custom_price: finalPrice,
        }),
      })
    } catch {
      // Already updated optimistically
    }
  }

  // Handle Shelf Image Upload & YOLO Simulation
  const handleShelfUpload = async (file?: File) => {
    setIsScanning(true)
    setScanResultBanner(null)

    if (file) {
      const formData = new FormData()
      formData.append("file", file)
      try {
        await fetch(`${API_BASE}/upload-shelf`, {
          method: "POST",
          body: formData,
        })
      } catch {
        // Ignore network error during simulation
      }
    }

    setTimeout(() => {
      setIsScanning(false)
      setScanResultBanner(
        "YOLOv8 Edge Scan Complete: 6 SKUs detected • 2 Overripe flagged • 1 Spoiled safety lock triggered"
      )
      showToast("Edge Camera Inference Complete: Shelf state synchronized!")
      fetchInventory()
    }, 1800)
  }

  const filteredItems =
    categoryFilter === "ALL"
      ? items
      : items.filter((i) => i.category.toLowerCase() === categoryFilter.toLowerCase())

  // Only show approved, non-spoiled items that have SLM promotional content on the Customer Phone App
  const customerPromos = items.filter(
    (i) =>
      i.approval_status === "APPROVED" &&
      i.freshness_status !== "Spoiled" &&
      i.slm_generated !== null
  )

  const approvedCount = items.filter((i) => i.approval_status === "APPROVED").length

  return (
    <main className="app-shell" style={{ minHeight: "100vh", paddingBottom: "48px" }}>
      {/* Live Toast Notification */}
      {toastMsg && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            right: 24,
            zIndex: 9999,
            background: "rgba(16, 185, 129, 0.95)",
            color: "#042f2e",
            padding: "12px 20px",
            borderRadius: "12px",
            fontWeight: 600,
            fontSize: "14px",
            boxShadow: "0 12px 32px rgba(16, 185, 129, 0.35)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
          }}
        >
          <CheckCircle2 size={18} />
          {toastMsg}
        </div>
      )}

      {/* Top Navigation Bar */}
      <header className="topbar">
        <div className="brand">
          <div className="logo-mark">
            <Leaf size={18} />
          </div>
          <span style={{ fontWeight: 700, fontSize: "18px", letterSpacing: "-0.02em" }}>
            fresh<span style={{ color: "#34d399" }}>-guard</span>
          </span>
          <span
            style={{
              fontSize: "11px",
              letterSpacing: "0.08em",
              opacity: 0.6,
              marginLeft: "8px",
              textTransform: "uppercase",
            }}
          >
            Autonomous Retail Intelligence
          </span>
        </div>

        <div className="topbar-center" style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div className="store-selector" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Store size={15} style={{ color: "#34d399" }} />
            <span>Mumbai Central Dark Store #01</span>
            <ChevronDown size={14} style={{ opacity: 0.6 }} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#34d399" }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "#34d399",
                boxShadow: "0 0 10px #34d399",
              }}
            />
            FastAPI + Sub-20B SLM Live
          </div>
        </div>

        <div className="topbar-actions" style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button className="icon-button" aria-label="Notifications" onClick={() => showToast("All edge cameras synced.")}>
            <Bell size={17} />
          </button>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "rgba(52, 211, 153, 0.18)",
              border: "1px solid rgba(52, 211, 153, 0.4)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "12px",
              fontWeight: 700,
              color: "#34d399",
            }}
          >
            AS
          </div>
        </div>
      </header>

      {/* View Switcher Bar */}
      <nav className="view-switcher" aria-label="View switcher" style={{ margin: "16px auto" }}>
        <button
          className={viewMode === "manager" ? "active" : ""}
          onClick={() => setViewMode("manager")}
        >
          <ShieldCheck size={15} />
          Store Manager Portal
        </button>
        <button
          className={viewMode === "customer" ? "active" : ""}
          onClick={() => setViewMode("customer")}
        >
          <Smartphone size={15} />
          Customer Loyalty App ({customerPromos.length})
        </button>
        <button
          className={`split-button ${viewMode === "split" ? "active" : ""}`}
          onClick={() => setViewMode("split")}
        >
          <Columns2 size={15} />
          Split Screen Demo Mode
        </button>
      </nav>

      {/* Main Layout Container */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: viewMode === "split" ? "1fr 410px" : "1fr",
          gap: "28px",
          maxWidth: viewMode === "split" ? "1440px" : "1180px",
          margin: "0 auto",
          padding: "0 24px",
          alignItems: "start",
        }}
      >
        {/* LEFT / MAIN PANEL: STORE MANAGER PORTAL */}
        {(viewMode === "manager" || viewMode === "split") && (
          <div className="page-content">
            <section style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "20px" }}>
              <div>
                <div style={{ fontSize: "11px", letterSpacing: "0.1em", color: "#34d399", textTransform: "uppercase", marginBottom: "4px" }}>
                  — Live Operations Center
                </div>
                <h1 style={{ fontSize: "34px", fontWeight: 700, margin: 0 }}>
                  Good morning, <span style={{ color: "#34d399" }}>Arpit.</span>
                </h1>
                <p style={{ opacity: 0.65, fontSize: "14px", marginTop: "4px" }}>
                  Autonomous YOLOv8 shelf auditing + tag-based cross-merchandising is protecting store margin.
                </p>
              </div>
              <div style={{ fontSize: "12px", color: "#34d399", display: "flex", alignItems: "center", gap: "6px" }}>
                ● All guardrails active <span style={{ opacity: 0.5, color: "#fff" }}>• Cost + 5% Floor</span>
              </div>
            </section>

            {/* KPI Cards */}
            <section className="metric-grid">
              <div className="metric-card">
                <div className="metric-icon">
                  <PackageCheck size={17} />
                </div>
                <div style={{ fontSize: "12px", opacity: 0.65, marginTop: "10px" }}>Monitored Batch SKUs</div>
                <div style={{ fontSize: "28px", fontWeight: 700, margin: "4px 0" }}>{items.length} Active</div>
                <div className="metric-detail">
                  <span className="trend-up" style={{ color: "#34d399", display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <TrendingUp size={12} /> 100%
                  </span>{" "}
                  vision coverage
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-icon">
                  <TriangleAlert size={17} />
                </div>
                <div style={{ fontSize: "12px", opacity: 0.65, marginTop: "10px" }}>Actionable Alerts</div>
                <div style={{ fontSize: "28px", fontWeight: 700, margin: "4px 0" }}>
                  {items.filter((i) => i.freshness_status === "Overripe" || i.freshness_status === "Spoiled").length} Flagged
                </div>
                <div className="metric-detail">
                  <span style={{ color: "#fbbf24" }}>2 Overripe • 1 Spoiled Lock</span>
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-icon">
                  <CircleDollarSign size={17} />
                </div>
                <div style={{ fontSize: "12px", opacity: 0.65, marginTop: "10px" }}>Protected Profit Margin</div>
                <div style={{ fontSize: "28px", fontWeight: 700, margin: "4px 0" }}>
                  ₹{(18.4 + approvedCount * 0.45).toFixed(1)}k
                </div>
                <div className="metric-detail">
                  <span className="trend-up" style={{ color: "#34d399", display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <TrendingUp size={12} /> +14.2%
                  </span>{" "}
                  via tag bundles
                </div>
              </div>

              <div className="metric-card">
                <div className="metric-icon">
                  <Leaf size={17} />
                </div>
                <div style={{ fontSize: "12px", opacity: 0.65, marginTop: "10px" }}>Waste Prevented</div>
                <div style={{ fontSize: "28px", fontWeight: 700, margin: "4px 0" }}>
                  {(124.0 + approvedCount * 1.4).toFixed(1)} kg
                </div>
                <div className="metric-detail">
                  <span className="trend-up" style={{ color: "#34d399", display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <TrendingUp size={12} /> {approvedCount} deals
                  </span>{" "}
                  live on app
                </div>
              </div>
            </section>

            {/* Operations Row: Edge Camera Dropzone + Interactive AI Recommendation Inspector */}
            <section className="operations-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginTop: "20px" }}>
              {/* Left: Shelf Scan with Interactive YOLO Bounding Boxes */}
              <div className="scan-card" style={{ position: "relative", overflow: "hidden" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                  <div className="section-kicker" style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "#34d399" }}>
                    <Camera size={13} /> EDGE CAMERA INFERENCE (YOLOv8 + EfficientNet)
                  </div>
                  <span style={{ fontSize: "11px", color: "#34d399", fontWeight: 600 }}>
                    ● {isScanning ? "SCANNING..." : "READY"}
                  </span>
                </div>
                <h2 style={{ fontSize: "20px", fontWeight: 700, margin: "4px 0" }}>Shelf scan</h2>
                <p style={{ fontSize: "13px", opacity: 0.65, marginBottom: "14px" }}>
                  Upload an aisle frame to detect produce ripeness, bin density %, and margin-safe pricing.
                </p>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleShelfUpload(e.target.files[0])
                  }}
                />

                <div
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    border: "1px dashed rgba(52, 211, 153, 0.35)",
                    borderRadius: "14px",
                    padding: "28px 16px",
                    textAlign: "center",
                    cursor: "pointer",
                    background: isScanning ? "rgba(16, 185, 129, 0.08)" : "rgba(255,255,255,0.015)",
                    transition: "all 0.25s ease",
                  }}
                >
                  <div className="scan-orb" style={{ margin: "0 auto 10px" }}>
                    <ScanLine size={25} />
                  </div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>
                    {isScanning ? "Running YOLOv8 Bounding Box & Ripeness Check..." : "Drop shelf image here or click to simulate scan"}
                  </div>
                  <div style={{ fontSize: "12px", opacity: 0.55, marginTop: "4px" }}>
                    Supports JPG, PNG, Edge RTSP Frame • Sub-20B SLM Ready
                  </div>

                  {/* Simulated Bounding Box Pill Overlay */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center", marginTop: "14px" }}>
                    <span style={{ fontSize: "11px", padding: "4px 8px", borderRadius: "6px", background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.4)", color: "#fbbf24" }}>
                      [Box 1] Bananas: 35% Fresh (84% Stock)
                    </span>
                    <span style={{ fontSize: "11px", padding: "4px 8px", borderRadius: "6px", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.4)", color: "#34d399" }}>
                      [Box 2] Wheat Flour: 92% Stock
                    </span>
                    <span style={{ fontSize: "11px", padding: "4px 8px", borderRadius: "6px", background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.4)", color: "#f87171" }}>
                      [Box 3] Strawberries: 12% Spoiled (LOCKED)
                    </span>
                  </div>
                </div>

                {scanResultBanner && (
                  <div
                    style={{
                      marginTop: "12px",
                      padding: "8px 12px",
                      borderRadius: "8px",
                      background: "rgba(16, 185, 129, 0.12)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      fontSize: "12px",
                      color: "#34d399",
                    }}
                  >
                    ✓ {scanResultBanner}
                  </div>
                )}

                <div className="scan-footer" style={{ display: "flex", justifyContent: "space-between", marginTop: "14px", fontSize: "12px", opacity: 0.65 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Activity size={13} /> Vision model v2.4 active (94% mAP)
                  </span>
                  <span
                    onClick={() => handleShelfUpload()}
                    style={{ color: "#34d399", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}
                  >
                    Trigger Demo Scan <ArrowUpRight size={13} />
                  </span>
                </div>
              </div>

              {/* Right: Dynamic AI Recommendation Card (Updates when you click any row in table!) */}
              <div className="recommendation-card" style={{ border: "1px solid rgba(52, 211, 153, 0.28)", borderRadius: "16px", padding: "20px", background: "rgba(16, 185, 129, 0.04)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div className="ai-badge" style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "#34d399", fontWeight: 600 }}>
                    <Sparkles size={14} /> AI MERCHANDISING ENGINE • {selectedItem.item_id.toUpperCase()}
                  </div>
                  <span style={{ fontSize: "11px", opacity: 0.6 }}>Click any table row to inspect</span>
                </div>

                <h2 style={{ fontSize: "21px", fontWeight: 700, margin: "8px 0 6px" }}>
                  {selectedItem.freshness_status === "Spoiled"
                    ? "Safety Lock: Immediate Removal Required"
                    : "Turn ripeness into revenue."}
                </h2>
                <p style={{ fontSize: "13px", opacity: 0.75, lineHeight: 1.45, marginBottom: "14px" }}>
                  {selectedItem.merchandising_note}
                </p>

                {/* Tag Matchmaker Visual Pairing */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: "10px", alignItems: "center", marginBottom: "14px" }}>
                  <div style={{ padding: "10px 12px", borderRadius: "10px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ fontWeight: 600, fontSize: "13px" }}>{selectedItem.name}</div>
                    <div style={{ fontSize: "11px", opacity: 0.65, marginTop: "2px" }}>
                      {formatPct(selectedItem.current_stock_pct)} stock • {cleanLabel(selectedItem.freshness_status)}
                    </div>
                  </div>
                  <span style={{ color: "#34d399", fontWeight: 700 }}>+</span>
                  <div style={{ padding: "10px 12px", borderRadius: "10px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ fontWeight: 600, fontSize: "13px" }}>
                      {partnerItem ? partnerItem.name : "No Bundle Partner (Single SKU)"}
                    </div>
                    <div style={{ fontSize: "11px", opacity: 0.65, marginTop: "2px" }}>
                      {partnerItem ? `${formatPct(partnerItem.current_stock_pct)} stock • Anchor` : "Direct Action"}
                    </div>
                  </div>
                </div>

                {/* Margin Guardrail Badge */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
                  <span style={{ fontSize: "12px", color: "#34d399", display: "inline-flex", alignItems: "center", gap: 5 }}>
                    <Tag size={13} /> Matched Tag:{" "}
                    <strong>{selectedItem.tags[0]?.replace("tag_", "").toUpperCase() || "GENERAL"}</strong>
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "4px 10px",
                      borderRadius: "6px",
                      background: "rgba(245, 158, 11, 0.12)",
                      border: "1px solid rgba(245, 158, 11, 0.35)",
                      color: "#fbbf24",
                      fontWeight: 600,
                    }}
                  >
                    Margin Guardrail: Floor ₹{selectedItem.min_allowed_price.toFixed(2)} (Cost + 5%)
                  </span>
                </div>

                {/* Price Slider (Locked if Spoiled) */}
                {selectedItem.freshness_status !== "Spoiled" ? (
                  <div style={{ marginBottom: "14px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "12px", marginBottom: "4px" }}>
                      <span style={{ opacity: 0.7 }}>
                        Adjust Action Price (Original: ₹{selectedItem.original_price.toFixed(2)})
                      </span>
                      <span style={{ fontWeight: 700, fontSize: "16px", color: "#34d399" }}>
                        ₹{customPrice.toFixed(2)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={selectedItem.min_allowed_price}
                      max={selectedItem.original_price}
                      step={0.5}
                      value={customPrice}
                      onChange={(e) => setCustomPrice( parseFloat(e.target.value) )}
                      style={{ width: "100%", accentColor: "#34d399", cursor: "pointer" }}
                    />
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "10px",
                      borderRadius: "8px",
                      background: "rgba(239, 68, 68, 0.15)",
                      border: "1px solid rgba(239, 68, 68, 0.4)",
                      color: "#f87171",
                      fontSize: "12px",
                      marginBottom: "14px",
                      fontWeight: 600,
                    }}
                  >
                    🔒 Pricing Disabled: Item is Spoiled (Freshness {(selectedItem.freshness_score * 100).toFixed(0)}%). Locked to REMOVE FROM SHELF.
                  </div>
                )}

                <button
                  onClick={() => handleApprove(selectedItem, customPrice)}
                  disabled={selectedItem.freshness_status === "Spoiled"}
                  style={{
                    width: "100%",
                    padding: "12px",
                    borderRadius: "10px",
                    border: "none",
                    fontWeight: 700,
                    fontSize: "14px",
                    cursor: selectedItem.freshness_status === "Spoiled" ? "not-allowed" : "pointer",
                    background:
                      selectedItem.freshness_status === "Spoiled"
                        ? "rgba(239, 68, 68, 0.25)"
                        : selectedItem.approval_status === "APPROVED"
                        ? "#34d399"
                        : "linear-gradient(90deg, #10b981, #34d399)",
                    color: selectedItem.freshness_status === "Spoiled" ? "#fca5a5" : "#042f2e",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                  }}
                >
                  <Zap size={16} />
                  {selectedItem.freshness_status === "Spoiled"
                    ? "Blocked by Food Safety Guardrail"
                    : selectedItem.approval_status === "APPROVED"
                    ? "✓ Approved & Live on Customer App (Click to Update Price)"
                    : `Approve ${cleanLabel(selectedItem.recommended_action)} @ ₹${customPrice.toFixed(2)}`}
                </button>
              </div>
            </section>

            {/* Live Inventory Compliance Table */}
            <section className="inventory-section" style={{ marginTop: "24px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                <div>
                  <div style={{ fontSize: "11px", color: "#34d399", display: "flex", alignItems: "center", gap: 6 }}>
                    <ShieldCheck size={13} /> COMPLIANCE MONITOR (CLICK ANY ROW TO INSPECT OR APPROVE)
                  </div>
                  <h2 style={{ fontSize: "20px", fontWeight: 700, margin: "2px 0 0" }}>Live inventory compliance</h2>
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                  {["ALL", "Produce", "Dairy", "Pantry_Anchor"].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setCategoryFilter(cat)}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "8px",
                        fontSize: "12px",
                        border: "1px solid rgba(255,255,255,0.12)",
                        background: categoryFilter === cat ? "rgba(52, 211, 153, 0.2)" : "rgba(255,255,255,0.03)",
                        color: categoryFilter === cat ? "#34d399" : "#fff",
                        cursor: "pointer",
                      }}
                    >
                      {cat === "ALL" ? "All Categories" : cleanLabel(cat)}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", textAlign: "left", fontSize: "11px", opacity: 0.6 }}>
                      <th style={{ padding: "12px" }}>ITEM</th>
                      <th style={{ padding: "12px" }}>CATEGORY</th>
                      <th style={{ padding: "12px" }}>STOCK LEVEL</th>
                      <th style={{ padding: "12px" }}>FRESHNESS</th>
                      <th style={{ padding: "12px" }}>ORIGINAL / ACTION PRICE</th>
                      <th style={{ padding: "12px" }}>RECOMMENDED ACTION</th>
                      <th style={{ padding: "12px", textAlign: "right" }}>MANAGER ACTION</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item) => {
                      const pctNumber = Math.round(
                        item.current_stock_pct <= 1 ? item.current_stock_pct * 100 : item.current_stock_pct
                      )
                      const isSelected = item.item_id === selectedItem.item_id

                      return (
                        <tr
                          key={item.item_id}
                          onClick={() => setSelectedItemId(item.item_id)}
                          style={{
                            borderBottom: "1px solid rgba(255,255,255,0.06)",
                            background: isSelected ? "rgba(52, 211, 153, 0.08)" : "transparent",
                            cursor: "pointer",
                            transition: "background 0.15s ease",
                          }}
                        >
                          <td style={{ padding: "14px 12px", fontWeight: 600 }}>
                            <div>{item.name}</div>
                            <div style={{ fontSize: "11px", opacity: 0.55 }}>
                              Floor: ₹{item.min_allowed_price.toFixed(2)} (Cost ₹{item.cost_price.toFixed(2)})
                            </div>
                          </td>
                          <td style={{ padding: "14px 12px", opacity: 0.8 }}>{cleanLabel(item.category)}</td>
                          <td style={{ padding: "14px 12px", minWidth: "150px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <div
                                style={{
                                  flex: 1,
                                  height: "6px",
                                  background: "rgba(255,255,255,0.1)",
                                  borderRadius: "999px",
                                  overflow: "hidden",
                                }}
                              >
                                <div
                                  style={{
                                    width: `${Math.min(100, pctNumber)}%`,
                                    height: "100%",
                                    background: pctNumber < 20 ? "#f87171" : pctNumber > 80 ? "#fbbf24" : "#34d399",
                                    borderRadius: "999px",
                                  }}
                                />
                              </div>
                              <span style={{ fontSize: "12px", fontWeight: 600, minWidth: "38px" }}>
                                {pctNumber}%
                              </span>
                            </div>
                            <div style={{ fontSize: "11px", opacity: 0.5, marginTop: "2px" }}>
                              {item.stock_count} / {item.shelf_capacity} units
                            </div>
                          </td>
                          <td style={{ padding: "14px 12px" }}>
                            <span
                              style={{
                                padding: "4px 10px",
                                borderRadius: "999px",
                                fontSize: "11px",
                                fontWeight: 600,
                                background:
                                  item.freshness_status === "Spoiled"
                                    ? "rgba(239, 68, 68, 0.18)"
                                    : item.freshness_status === "Overripe"
                                    ? "rgba(245, 158, 11, 0.18)"
                                    : "rgba(16, 185, 129, 0.18)",
                                color:
                                  item.freshness_status === "Spoiled"
                                    ? "#f87171"
                                    : item.freshness_status === "Overripe"
                                    ? "#fbbf24"
                                    : "#34d399",
                              }}
                            >
                              ● {cleanLabel(item.freshness_status)} ({Math.round(item.freshness_score * 100)}%)
                            </span>
                          </td>
                          <td style={{ padding: "14px 12px" }}>
                            <div style={{ fontWeight: 700 }}>
                              {item.freshness_status === "Spoiled"
                                ? "BLOCKED"
                                : money(item.recommended_price ?? item.original_price)}
                            </div>
                            <div style={{ fontSize: "11px", opacity: 0.5, textDecoration: "line-through" }}>
                              ₹{item.original_price.toFixed(2)}
                            </div>
                          </td>
                          <td style={{ padding: "14px 12px", fontWeight: 600, fontSize: "12px" }}>
                            <span
                              style={{
                                color:
                                  item.freshness_status === "Spoiled"
                                    ? "#f87171"
                                    : item.approval_status === "APPROVED"
                                    ? "#34d399"
                                    : "#fbbf24",
                              }}
                            >
                              {cleanLabel(item.recommended_action)}
                            </span>
                          </td>
                          <td style={{ padding: "14px 12px", textAlign: "right" }}>
                            {item.freshness_status === "Spoiled" ? (
                              <span style={{ fontSize: "11px", color: "#f87171", fontWeight: 600 }}>
                                Safety Locked
                              </span>
                            ) : item.approval_status === "APPROVED" ? (
                              <span
                                style={{
                                  padding: "5px 10px",
                                  borderRadius: "8px",
                                  background: "rgba(16, 185, 129, 0.15)",
                                  color: "#34d399",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                }}
                              >
                                ✓ Approved
                              </span>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleApprove(item)
                                }}
                                style={{
                                  padding: "6px 12px",
                                  borderRadius: "8px",
                                  border: "1px solid #34d399",
                                  background: "rgba(16, 185, 129, 0.15)",
                                  color: "#34d399",
                                  fontSize: "11px",
                                  fontWeight: 700,
                                  cursor: "pointer",
                                }}
                              >
                                Approve Deal
                              </button>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Safety Guardrail Footer Banner */}
              <div className="guardrail" style={{ marginTop: "16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <LockKeyhole size={18} style={{ color: "#fbbf24" }} />
                  <div style={{ fontSize: "12px" }}>
                    <strong>Zero-Trust Food Safety & Margin Guardrail Active:</strong> Any item classified as{" "}
                    <code style={{ color: "#f87171" }}>Spoiled</code> is automatically locked to{" "}
                    <code style={{ color: "#f87171" }}>REMOVE_FROM_SHELF</code> and blocked from customer loyalty feeds.
                  </div>
                </div>
                <ShieldCheck size={18} style={{ color: "#34d399" }} />
              </div>
            </section>
          </div>
        )}

        {/* RIGHT PANEL: CUSTOMER LOYALTY MOBILE APP */}
        {(viewMode === "customer" || viewMode === "split") && (
          <div style={{ position: viewMode === "split" ? "sticky" : "static", top: "24px" }}>
            <div style={{ textAlign: "center", marginBottom: "16px" }}>
              <div style={{ fontSize: "11px", letterSpacing: "0.1em", color: "#34d399", textTransform: "uppercase" }}>
                — Customer Experience Preview
              </div>
              <h2 style={{ fontSize: "26px", fontWeight: 700, margin: "4px 0" }}>
                Fresh finds, <span style={{ color: "#34d399" }}>zero waste.</span>
              </h2>
              <p style={{ fontSize: "12px", opacity: 0.65 }}>
                Live shopper loyalty feed powered by sub-20B SLM recipes & approved manager actions.
              </p>
            </div>

            {/* Mobile Phone Mockup Frame */}
            <div
              style={{
                width: "380px",
                margin: "0 auto",
                borderRadius: "36px",
                border: "6px solid rgba(255,255,255,0.12)",
                background: "#071311",
                padding: "18px 16px",
                boxShadow: "0 24px 60px rgba(0,0,0,0.65)",
              }}
            >
              {/* Phone Status Bar */}
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", opacity: 0.7, marginBottom: "14px", padding: "0 6px" }}>
                <span>9:41</span>
                <span>5G • 100%</span>
              </div>

              {/* Phone App Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div className="logo-mark" style={{ width: 28, height: 28 }}>
                    <Leaf size={14} />
                  </div>
                  <span style={{ fontWeight: 700, fontSize: "15px" }}>
                    fresh<span style={{ color: "#34d399" }}>-guard</span>
                  </span>
                </div>
                <span style={{ fontSize: "11px", padding: "4px 8px", borderRadius: "999px", background: "rgba(52, 211, 153, 0.15)", color: "#34d399" }}>
                  Mumbai Central
                </span>
              </div>

              <div style={{ marginBottom: "14px" }}>
                <div style={{ fontSize: "12px", opacity: 0.65 }}>Good morning, Priya</div>
                <div style={{ fontSize: "20px", fontWeight: 700 }}>Made fresh for you.</div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", opacity: 0.6, marginBottom: "10px" }}>
                <span>JUST FOR YOU (SLM GENERATED)</span>
                <span>{customerPromos.length} live bundles</span>
              </div>

              {/* Scrollable Customer Deal Cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "470px", overflowY: "auto", paddingRight: "4px" }}>
                {customerPromos.map((deal) => {
                  const discountPct =
                    deal.recommended_price && deal.recommended_price < deal.original_price
                      ? Math.round(((deal.original_price - deal.recommended_price) / deal.original_price) * 100)
                      : 0
                  const isExpanded = expandedRecipeId === deal.item_id

                  return (
                    <div
                      key={deal.item_id}
                      style={{
                        borderRadius: "18px",
                        padding: "16px",
                        background: "linear-gradient(145deg, rgba(16, 185, 129, 0.16), rgba(6, 78, 59, 0.28))",
                        border: "1px solid rgba(52, 211, 153, 0.3)",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <span style={{ fontSize: "10px", fontWeight: 700, color: "#fbbf24", letterSpacing: "0.06em" }}>
                          🔥 {deal.slm_generated?.discount_badge || "FLASH BUNDLE"}
                        </span>
                        <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "999px", border: "1px solid rgba(52,211,153,0.4)", color: "#34d399" }}>
                          LIVE NOW
                        </span>
                      </div>

                      {/* Real Customer SLM Headline (Fixes the Internal Note Leak!) */}
                      <div style={{ fontSize: "16px", fontWeight: 700, lineHeight: 1.3, marginBottom: "6px" }}>
                        {deal.slm_generated?.headline}
                      </div>

                      <div style={{ fontSize: "12px", opacity: 0.8, marginBottom: "10px" }}>
                        Includes <strong>{deal.name}</strong>{" "}
                        {deal.bundle_partner_id ? "+ Paired Store Anchor Combo" : ""}
                      </div>

                      {/* Price & Discount Row */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "10px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                        <div>
                          <div style={{ fontSize: "18px", fontWeight: 800, color: "#34d399" }}>
                            ₹{(deal.recommended_price ?? deal.original_price).toFixed(2)}{" "}
                            {discountPct > 0 && (
                              <span style={{ fontSize: "12px", color: "#fbbf24", fontWeight: 700 }}>
                                ({discountPct}% OFF)
                              </span>
                            )}
                          </div>
                          {discountPct > 0 && (
                            <div style={{ fontSize: "11px", opacity: 0.5, textDecoration: "line-through" }}>
                              MRP ₹{deal.original_price.toFixed(2)}
                            </div>
                          )}
                        </div>

                        <button
                          onClick={() => setExpandedRecipeId(isExpanded ? null : deal.item_id)}
                          style={{
                            padding: "8px 12px",
                            borderRadius: "10px",
                            border: "none",
                            background: "#34d399",
                            color: "#042f2e",
                            fontWeight: 700,
                            fontSize: "11px",
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                          }}
                        >
                          <ChefHat size={14} />
                          {isExpanded ? "Hide Recipe" : "10-Min Recipe"}
                        </button>
                      </div>

                      {/* Expandable SLM Zero-Waste Recipe Card */}
                      {isExpanded && deal.slm_generated && (
                        <div
                          style={{
                            marginTop: "10px",
                            padding: "10px 12px",
                            borderRadius: "12px",
                            background: "rgba(0,0,0,0.35)",
                            fontSize: "12px",
                          }}
                        >
                          <div style={{ fontWeight: 700, color: "#34d399", marginBottom: "6px" }}>
                            🍲 {deal.slm_generated.recipe_title}
                          </div>
                          <div style={{ fontSize: "11px", opacity: 0.75, marginBottom: "6px" }}>
                            <strong>Ingredients:</strong> {deal.slm_generated.ingredients.join(" • ")}
                          </div>
                          <ol style={{ margin: 0, paddingLeft: "16px", fontSize: "11px", opacity: 0.85, lineHeight: 1.45 }}>
                            {deal.slm_generated.instructions.map((step, idx) => (
                              <li key={idx} style={{ marginBottom: "3px" }}>
                                {step}
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Fixed Bottom Navigation Inside Phone Bezel */}
              <div
                style={{
                  marginTop: "14px",
                  paddingTop: "10px",
                  borderTop: "1px solid rgba(255,255,255,0.1)",
                  display: "flex",
                  justifyContent: "space-around",
                  fontSize: "11px",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", color: "#34d399", fontWeight: 600 }}>
                  <Leaf size={15} />
                  <span style={{ marginTop: 2 }}>Deals</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", opacity: 0.6 }}>
                  <ChefHat size={15} />
                  <span style={{ marginTop: 2 }}>Recipes</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", opacity: 0.6 }}>
                  <Tag size={15} />
                  <span style={{ marginTop: 2 }}>Loyalty Pass</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  )
}