// Builds report/slides/WQI_Reduced_Parameters.pptx (15 slides) with pptxgenjs.
// Run: NODE_PATH=<dir with pptxgenjs>/node_modules node report/slides/build_deck.js
// Numbers are taken from results/*.csv (see the report for full detail).

const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..", "..");
const FIG = (f) => path.join(ROOT, "figures", f);
const OUT = path.join(__dirname, "WQI_Reduced_Parameters.pptx");
const APPLY_THEME = process.env.APPLY_THEME;

const THEME = {
  name: "River",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "13293D", lt1: "FFFFFF", dk2: "0B4F6C", lt2: "E8F3F4",
    accent1: "1A7F8E", accent2: "F2A541", accent3: "D1495B", accent4: "66A182",
    accent5: "8A9BA8", accent6: "0B4F6C", hlink: "1A7F8E", folHlink: "5B3758",
  },
};
const H = THEME.colors; // hex, for hex-only chart options

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.title = "Reduced-Parameter WQI Prediction for Data-Scarce River Systems";
pres.author = "Mayank Tiwari, Krupa Marol, Srushti Dongre, Sreenidhi Golamaru, Bharath Chowdary";
pres.subject = "CV301 Environmental Engineering, NITK Surathkal";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text2 },
  objects: [],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 12.1, h: 0.95,
      fontSize: 30, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: "CV301 Environmental Engineering · NITK Surathkal · Reduced-parameter WQI",
      options: { x: 0.6, y: 7.05, w: 9, h: 0.3, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.05, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
});

// ------------------------------------------------------------------ helpers
let currentSection = null;
function slide(master, section) {
  if (section !== currentSection) {
    pres.addSection({ title: section });
    currentSection = section;
  }
  return pres.addSlide({ masterName: master, sectionTitle: section });
}
function title(s, text) {
  s.addText(text, { placeholder: "title" });
}
function card(s, x, y, w, h, name, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill || C.background2 }, line: { color: fill || C.background2 },
    objectName: name,
  });
}
function stat(s, x, y, w, big, label, color, name) {
  s.addText(big, { x, y, w, h: 0.85, fontSize: 40, bold: true, color: color || C.text2, margin: 0,
    fontFace: THEME.headFontFace, isTextBox: true, objectName: name + " value" });
  s.addText(label, { x, y: y + 0.85, w, h: 0.6, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: name + " label" });
}
function badge(s, x, y, n, name) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.45, h: 0.45, fill: { color: C.accent1 }, line: { color: C.accent1 },
    objectName: name + " badge" });
  s.addText(String(n), { x, y, w: 0.45, h: 0.45, fontSize: 14, bold: true, color: C.background1, align: "center",
    valign: "middle", margin: 0, isTextBox: true, objectName: name + " number" });
}
function body(s, runs, opts) {
  s.addText(runs, Object.assign({ fontSize: 15, color: C.text1, valign: "top", margin: 0, isTextBox: true,
    paraSpaceAfter: 6 }, opts));
}
function bullets(items) {
  return items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } }));
}
const AXIS = { catAxisLabelColor: H.dk1, valAxisLabelColor: H.dk1, catAxisLabelFontSize: 12,
  valAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  dataLabelFontFace: "+mn-lt", dataLabelFontSize: 11, dataLabelColor: H.dk1,
  titleFontFace: "+mn-lt", legendFontFace: "+mn-lt", legendFontSize: 12,
  valGridLine: { color: "D9E2E6", size: 0.75 }, catGridLine: { style: "none" } };
const chartOpts = (extra) => Object.assign({}, AXIS, extra);

// =================================================================== 1 Title
{
  const s = slide("DARK", "Opening");
  card(s, 0.7, 1.35, 3.6, 3.9, "Logo card", C.background1);
  s.addImage({ path: path.join(ROOT, "image.png"), x: 1.05, y: 1.75, w: 2.9, h: 2.74, objectName: "NITK logo" });
  s.addText("NATIONAL INSTITUTE OF TECHNOLOGY KARNATAKA, SURATHKAL", { x: 0.7, y: 0.45, w: 12, h: 0.45,
    fontSize: 16, bold: true, color: C.accent2, margin: 0, charSpacing: 1, isTextBox: true, objectName: "Institute" });
  s.addText("Reduced-Parameter Water Quality Index Prediction for Data-Scarce River Systems", {
    x: 4.8, y: 1.3, w: 7.9, h: 1.9, fontSize: 34, bold: true, color: C.background1, fontFace: THEME.headFontFace,
    margin: 0, valign: "top", isTextBox: true, objectName: "Deck title" });
  s.addText("Evidence from 32,968 CPCB river monitoring visits, 2018–2021", { x: 4.8, y: 3.25, w: 7.9, h: 0.45,
    fontSize: 18, italic: true, color: C.background2, margin: 0, isTextBox: true, objectName: "Subtitle" });
  s.addText([
    { text: "Course: ", options: { bold: true, color: C.accent2 } },
    { text: "CV301 Environmental Engineering", options: { breakLine: true } },
    { text: "Faculty: ", options: { bold: true, color: C.accent2 } },
    { text: "Saranya P" },
  ], { x: 4.8, y: 4.0, w: 7.9, h: 0.75, fontSize: 16, color: C.background1, margin: 0, isTextBox: true,
    objectName: "Course and faculty" });
  const team = [["Mayank Tiwari", "241CV235"], ["Krupa Marol", "241CV231"], ["Srushti Dongre", "241CV248"],
    ["Sreenidhi Golamaru", "241CV247"], ["Bharath Chowdary", "241CV213"]];
  s.addText("Team", { x: 4.8, y: 5.0, w: 3, h: 0.35, fontSize: 14, bold: true, color: C.accent2, margin: 0,
    isTextBox: true, objectName: "Team heading" });
  team.forEach(([n, r], i) => {
    const col = i < 3 ? 0 : 1;
    const row = i < 3 ? i : i - 3;
    s.addText([{ text: n + "  ", options: { bold: true } }, { text: r, options: { color: C.background2 } }], {
      x: 4.8 + col * 3.9, y: 5.4 + row * 0.38, w: 3.8, h: 0.36, fontSize: 14, color: C.background1, margin: 0,
      isTextBox: true, objectName: "Team member " + (i + 1) });
  });
  s.addNotes("Introduce the team and the question: can a few cheap, routinely measured parameters stand in for the full eight-parameter panel that a Water Quality Index needs? Everything shown uses real CPCB data from the National Water Data Portal.");
}

// =================================================================== 2 Problem
{
  const s = slide("CONTENT", "Problem & data");
  title(s, "Only 15% of river visits can compute a full WQI");
  stat(s, 0.6, 1.55, 3.6, "14.7%", "of 32,968 river visits report all 8 WQI parameters", C.accent3, "Full panel share");
  stat(s, 0.6, 3.15, 3.6, "75.8%", "report pH, DO and BOD, the three best-covered parameters", C.accent1, "S3 share");
  card(s, 0.6, 4.85, 3.9, 1.5, "Research question card");
  s.addText([
    { text: "Research question", options: { bold: true, color: C.text2, breakLine: true } },
    { text: "Can reduced-parameter monitoring provide reliable WQI prediction for data-scarce river systems?", options: { italic: true } },
  ], { x: 0.8, y: 4.98, w: 3.5, h: 1.6, fontSize: 15, color: C.text1, margin: 0, valign: "top", isTextBox: true,
    objectName: "Research question" });
  s.addChart(pres.charts.BAR, [{
    name: "Visits",
    labels: ["All river visits", "pH, DO, BOD", "+ Fecal coliform", "+ EC", "+ Total coli., turbidity", "All 8 (WQI computable)"],
    values: [32968, 24993, 21547, 5961, 5256, 4861],
  }], chartOpts({
    x: 4.9, y: 1.45, w: 7.8, h: 5.3, barDir: "bar", catAxisOrientation: "maxMin",
    chartColors: [H.accent1],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", valAxisHidden: true,
    showTitle: true, title: "River visits reporting each nested parameter set", titleFontSize: 14, titleColor: H.dk1,
    showLegend: false, barGapWidthPct: 45, objectName: "Funnel chart",
  }));
  s.addNotes("CPCB visits rarely report the full panel. Three quarters report pH, DO and BOD, but only 14.7 percent report all eight parameters, so most visits never get a WQI. If a model can recover the full-panel index from the reduced panel, the index becomes available for about five times as many visits.");
}

// =================================================================== 3 Data
{
  const s = slide("CONTENT", "Problem & data");
  title(s, "The full panel was recorded in one year only");
  s.addImage({ path: FIG("fig_eda_fill_by_year.png"), x: 0.6, y: 1.5, w: 7.3, h: 7.3 * 626 / 1213,
    objectName: "Fill rate heatmap" });
  s.addText("Fill rate (% of river visits) by parameter and year", { x: 0.6, y: 5.42, w: 7.3, h: 0.3, fontSize: 11,
    color: C.accent5, margin: 0, isTextBox: true, objectName: "Heatmap caption" });
  const steps = [
    ["211 raw CSVs", "physical, chemical and biological tables (57\u00A0MB)"],
    ["32,968 river visits", "888 stations, 87 rivers, joined and audited"],
    ["4,861 labelled visits", "593 stations with all 8 parameters, all in 2020"],
  ];
  steps.forEach(([h, d], i) => {
    const y = 1.5 + i * 1.25;
    card(s, 8.3, y, 4.4, 1.05, "Pipeline step " + (i + 1));
    badge(s, 8.45, y + 0.3, i + 1, "Pipeline step " + (i + 1));
    s.addText([{ text: h, options: { bold: true, breakLine: true, color: C.text2 } }, { text: d, options: { fontSize: 13 } }],
      { x: 9.05, y: y + 0.12, w: 3.55, h: 0.85, fontSize: 16, color: C.text1, margin: 0, valign: "middle",
        isTextBox: true, objectName: "Pipeline step " + (i + 1) + " text" });
  });
  body(s, [{ text: "EC, coliforms, turbidity and nitrate were logged almost only in 2020. Other years carry a routine pH–DO–BOD–coliform panel: a real, not simulated, data-scarce setting.", options: {} }],
    { x: 8.3, y: 5.4, w: 4.4, h: 1.3, fontSize: 14 });
  s.addNotes("We downloaded 211 CSV files, joined physical, chemical and biological tables on station and date, filtered to rivers, and audited the pipeline. The most important finding: four of the eight parameters were recorded almost exclusively in 2020, so the ground truth exists for one year only, while 2018, 2019 and 2021 are naturally data-scarce.");
}

// =================================================================== 4 WQI drivers
{
  const s = slide("CONTENT", "Problem & data");
  title(s, "pH and BOD drive 87.5% of the CPCB index");
  s.addChart(pres.charts.BAR, [{
    name: "Share of WQI variance (%)",
    labels: ["pH", "BOD", "Turbidity", "DO", "Nitrate-N", "Fecal coliform", "EC", "Total coliform"],
    values: [51.1, 36.4, 7.3, 3.6, 1.3, 0.19, 0.04, 0.02],
  }], chartOpts({
    x: 0.6, y: 1.45, w: 7.4, h: 5.3, barDir: "bar", catAxisOrientation: "maxMin", chartColors: [H.accent1],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0#", valAxisHidden: true,
    showTitle: true, title: "Exact share of index variance per parameter (%)", titleFontSize: 14, titleColor: H.dk1,
    showLegend: false, barGapWidthPct: 40, objectName: "Variance share chart",
  }));
  card(s, 8.4, 1.5, 4.3, 1.75, "Formula card");
  s.addText([
    { text: "CPCB weighted-arithmetic WQI", options: { bold: true, color: C.text2, breakLine: true } },
    { text: "WQI = Σ Wᵢ·qᵢ / Σ Wᵢ,  with qᵢ capped at 100", options: { breakLine: true } },
    { text: "Unit weight Wᵢ ∝ 1 / Sᵢ (Sᵢ = standard)", options: {} },
  ], { x: 8.6, y: 1.65, w: 3.9, h: 2.0, fontSize: 15, color: C.text1, margin: 0, valign: "top", paraSpaceAfter: 8,
    isTextBox: true, objectName: "Formula text" });
  s.addText("Fecal coliform exceeds its bathing standard on 34% of visits, yet explains 0.2% of the index.", {
    x: 8.4, y: 4.15, w: 4.3, h: 1.2, fontSize: 18, italic: true, bold: true, color: C.accent3, margin: 0,
    isTextBox: true, objectName: "Coliform callout" });
  body(s, [{ text: "Weights ∝ 1/Sᵢ reward parameters whose standard is a small number: 2 pH units or 3 mg/L, versus 500 MPN/100 mL.", options: {} }],
    { x: 8.4, y: 5.5, w: 4.3, h: 1.2, fontSize: 14 });
  s.addNotes("Because the index is linear in the capped sub-indices, its variance decomposes exactly. pH and BOD explain 87.5 percent; the coliforms and EC together explain under 0.3 percent. This is arithmetic, not hydrology: the weights are inversely proportional to the numeric value of each standard.");
}

// =================================================================== 5 Approach
{
  const s = slide("CONTENT", "Method");
  title(s, "Approach: learn the full-panel WQI from a few inputs");
  s.addImage({ path: path.join(ROOT, "report", "latex", "diagrams", "surrogate.png"), x: 1.2, y: 1.35, w: 7.6,
    h: 7.6 * 714 / 1424, objectName: "Surrogate diagram" });
  const cards = [
    ["8 model families", "Formula (no ML), Linear, kNN, SVR, MLP, Random Forest, XGBoost, Gaussian process"],
    ["12 named + all 255 subsets", "3, 4, 5, 7 and 8 parameters; availability-, importance- and sensor-based"],
    ["5 validation schemes", "random rows, unseen stations (primary), unseen rivers, states, season"],
  ];
  cards.forEach(([h, d], i) => {
    const x = 0.6 + i * 4.1;
    card(s, x, 5.35, 3.9, 1.3, "Method card " + (i + 1));
    s.addText([{ text: h, options: { bold: true, color: C.text2, breakLine: true } }, { text: d, options: { fontSize: 13 } }],
      { x: x + 0.2, y: 5.45, w: 3.5, h: 1.25, fontSize: 16, color: C.text1, margin: 0, valign: "top",
        isTextBox: true, objectName: "Method card " + (i + 1) + " text" });
  });
  body(s, [{ text: "The target never changes: every model predicts the same full-panel WQI, so subset sizes are compared fairly.", options: {} }],
    { x: 9.1, y: 1.6, w: 3.6, h: 3.2, fontSize: 16 });
  s.addNotes("Surrogate modelling: the ground truth is computed once from all eight parameters. Each model sees only a subset and is trained to reproduce that same target. Headline numbers use unseen stations, which mimics deploying at a new site.");
}

// =================================================================== 6 Importance
{
  const s = slide("CONTENT", "Results");
  title(s, "Importance: pH › BOD › turbidity › DO › nitrate");
  s.addChart(pres.charts.LINE, [{
    name: "R² on unseen stations",
    labels: ["pH", "+BOD", "+Turbidity", "+DO", "+Nitrate", "+EC", "+Fecal coli.", "+Total coli."],
    values: [0.508, 0.939, 0.977, 0.993, 0.998, 0.997, 0.997, 0.997],
  }], chartOpts({
    x: 0.6, y: 1.45, w: 7.6, h: 5.3, chartColors: [H.accent1], lineSize: 3, lineDataSymbolSize: 9,
    showValue: true, dataLabelPosition: "t", dataLabelFormatCode: "0.000", valAxisMinVal: 0.4, valAxisMaxVal: 1.1,
    valAxisMajorUnit: 0.1, valAxisLabelFormatCode: "0.0",
    showTitle: true, title: "Greedy forward selection (XGBoost, unseen stations)", titleFontSize: 14, titleColor: H.dk1,
    showLegend: false, objectName: "Forward selection chart",
  }));
  stat(s, 8.6, 1.55, 4.1, "0.94", "R² from pH and BOD alone", C.accent1, "Two param stat");
  stat(s, 8.6, 3.05, 4.1, "0", "R² lost when coliforms or EC are removed from the full model", C.accent3, "Drop column stat");
  body(s, [{ text: "Correlation ≠ importance: ", options: { bold: true } },
    { text: "the coliforms correlate with WQI (ρ ≈ 0.38) only because sewage raises BOD too. Seven methods agree on the order.", options: {} }],
    { x: 8.6, y: 4.75, w: 4.1, h: 1.9, fontSize: 15 });
  s.addNotes("Eight importance methods (correlation, mutual information, RF, XGBoost gain, permutation, SHAP, drop-column, analytic variance share) agree on the order. Forward selection reaches the ceiling at five parameters; the last three add nothing. Picking by correlation alone would have chosen the coliforms.");
}

// =================================================================== 7 Which beats how many
{
  const s = slide("CONTENT", "Results");
  title(s, "Choosing the right parameters beats adding more");
  s.addImage({ path: FIG("fig_comb_all_subsets.png"), x: 0.6, y: 1.4, w: 7.9, h: 7.9 * 813 / 1290,
    objectName: "All subsets chart" });
  const st = [["0.977", "best 3-parameter set: pH, BOD, turbidity", C.accent1],
    ["0.53", "median 3-parameter set", C.accent3],
    ["2nd / 56", "rank of the planned S3 (pH, DO, BOD): R² 0.957", C.text2]];
  st.forEach(([b, l, col], i) => stat(s, 8.9, 1.5 + i * 1.75, 3.8, b, l, col, "Subset stat " + (i + 1)));
  s.addNotes("All 255 subsets were scored on unseen stations. At three parameters, R-squared ranges from 0.26 to 0.98 depending on which three. The best three beat the median six. The planned S3 is second of 56; the planned S5 only 13th of 56 because it adds the near-weightless coliform and EC.");
}

// =================================================================== 8 ML vs formula
{
  const s = slide("CONTENT", "Results");
  title(s, "Machine learning clearly beats re-weighting the formula");
  s.addChart(pres.charts.BAR, [
    { name: "XGBoost", labels: ["S3", "S4-routine", "S5", "I3", "S7", "Sensor-4"], values: [0.957, 0.965, 0.967, 0.977, 0.994, 0.828] },
    { name: "Formula over available parameters", labels: ["S3", "S4-routine", "S5", "I3", "S7", "Sensor-4"], values: [0.863, 0.865, 0.866, 0.874, 0.903, 0.389] },
  ], chartOpts({
    x: 0.6, y: 1.45, w: 8.2, h: 5.3, barDir: "col", barGrouping: "clustered", chartColors: [H.accent1, H.accent5],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1.1,
    valAxisMajorUnit: 0.2, valAxisLabelFormatCode: "0.0", showLegend: true, legendPos: "b",
    showTitle: true, title: "R² on unseen stations", titleFontSize: 14, titleColor: H.dk1, barGapWidthPct: 60,
    objectName: "ML versus formula chart",
  }));
  body(s, bullets([
    "XGBoost is best for every subset; RF, MLP and GPR are close behind",
    "The subset matters far more than the model: for S3, flexible models span R² 0.934–0.957",
    "Linear regression fails (R² ≈ 0.74): the capped sub-indices are piecewise-linear",
    "The model learns the expected contribution of the missing parameters; the formula cannot",
  ]), { x: 9.2, y: 1.6, w: 3.5, h: 5.1, fontSize: 15, paraSpaceAfter: 10 });
  s.addNotes("The natural no-ML alternative is to evaluate the formula over the parameters you have, with renormalised weights. The model beats it everywhere, most dramatically for probe-only panels. The model estimates the missing turbidity and nitrate contribution from correlations, season and region.");
}

// =================================================================== 9 Headline accuracy
{
  const s = slide("CONTENT", "Results");
  title(s, "Three parameters predict the WQI at unseen stations");
  const st = [["0.957", "R² (NSE) for pH, DO, BOD"], ["2.9", "RMSE in WQI points (target s.d. 14.1)"],
    ["90.6%", "category accuracy (baseline 58%)"], ["0", "visits off by two or more categories"]];
  st.forEach(([b, l], i) => stat(s, 0.6 + i * 3.1, 1.45, 2.9, b, l, i === 3 ? C.accent4 : C.text2, "Headline " + (i + 1)));
  s.addImage({ path: FIG("fig_models_pred_vs_true.png"), x: 0.9, y: 3.15, w: 11.5, h: 11.5 * 640 / 1916,
    objectName: "Predicted versus true" });
  s.addNotes("With only pH, DO and BOD, the model reaches R-squared 0.957 at stations it has never seen, and every category error is to an adjacent class. Holding out whole rivers gives 0.942, whole states 0.943 and a whole season 0.949. Adding turbidity (S7 or I4) brings it to about 0.994.");
}

// =================================================================== 10 Scarcity
{
  const s = slide("CONTENT", "Results");
  title(s, "Models need ~25 training stations to beat the formula");
  const labels = ["9", "24", "47", "118", "237", "474"];
  s.addChart(pres.charts.LINE, [
    { name: "Formula (no training)", labels, values: [5.20, 5.20, 5.20, 5.20, 5.20, 5.20] },
    { name: "Gaussian process", labels, values: [5.92, 4.31, 3.90, 3.30, 3.21, 3.14] },
    { name: "XGBoost", labels, values: [6.56, 4.54, 3.95, 3.36, 3.11, 2.93] },
  ], chartOpts({
    x: 0.6, y: 1.45, w: 7.9, h: 5.3, chartColors: [H.accent5, H.accent2, H.accent1], lineSize: 3,
    lineDataSymbolSize: 8, valAxisMinVal: 2, valAxisMaxVal: 7, valAxisMajorUnit: 1,
    showValue: false, showLegend: true, legendPos: "b", showCatAxisTitle: true,
    catAxisTitle: "Training stations (S3, unseen test stations)", catAxisTitleFontSize: 12, catAxisTitleColor: H.dk1, catAxisTitleFontFace: "+mn-lt",
    showValAxisTitle: true, valAxisTitle: "RMSE (WQI points)", valAxisTitleFontSize: 12, valAxisTitleColor: H.dk1, valAxisTitleFontFace: "+mn-lt",
    showTitle: true, title: "Error as training data shrinks", titleFontSize: 14, titleColor: H.dk1,
    objectName: "Scarcity chart",
  }));
  const rows = [["< 25 stations", "use the formula"], ["25–100 stations", "Gaussian process"], ["> 100 stations", "XGBoost"]];
  rows.forEach(([a, b], i) => {
    const y = 1.6 + i * 1.15;
    card(s, 8.9, y, 3.8, 0.95, "Scarcity rule " + (i + 1));
    badge(s, 9.05, y + 0.25, i + 1, "Scarcity rule " + (i + 1));
    s.addText([{ text: a, options: { bold: true, color: C.text2, breakLine: true } }, { text: b, options: {} }],
      { x: 9.65, y: y + 0.1, w: 2.95, h: 0.75, fontSize: 15, color: C.text1, margin: 0, valign: "middle",
        isTextBox: true, objectName: "Scarcity rule " + (i + 1) + " text" });
  });
  body(s, [{ text: "Neural networks fail when data are scarce (R² < 0 with 9 stations). Extra parameters only pay off beyond about 50 stations.", options: {} }],
    { x: 8.9, y: 5.2, w: 3.8, h: 1.5, fontSize: 14 });
  s.addNotes("We kept 2 to 100 percent of the training stations while testing on the same unseen stations. Below about 25 stations no learned model beats the renormalised formula; GPR degrades most gracefully; XGBoost wins with more data. A sparsely monitored region gains more from more stations than from more parameters.");
}

// =================================================================== 11 Uncertainty and noise
{
  const s = slide("CONTENT", "Results");
  title(s, "Calibrated intervals; pH precision matters most");
  card(s, 0.6, 1.45, 4.6, 5.25, "Uncertainty card");
  s.addText("Split-conformal 90% intervals", { x: 0.85, y: 1.6, w: 4.1, h: 0.4, fontSize: 17, bold: true,
    color: C.text2, margin: 0, isTextBox: true, objectName: "Uncertainty heading" });
  stat(s, 0.85, 2.15, 4.1, "90.3%", "empirical coverage on unseen stations (S3)", C.accent1, "Coverage");
  stat(s, 0.85, 3.65, 4.1, "± 4.7", "WQI points for S3; ± 1.6 for S7", C.text2, "Half width");
  body(s, [{ text: "62% of visits get an interval inside a single category; the rest are flagged “category uncertain”.", options: {} }],
    { x: 0.85, y: 5.2, w: 4.1, h: 1.3, fontSize: 14 });
  s.addChart(pres.charts.BAR, [{
    name: "Full-8 RMSE",
    labels: ["No noise", "pH ±0.1", "BOD ±15%", "DO ±0.3 mg/L", "Turbidity ±10%", "Coliforms ±50%"],
    values: [0.76, 3.13, 2.11, 0.90, 0.80, 0.76],
  }], chartOpts({
    x: 5.6, y: 1.45, w: 7.1, h: 5.3, barDir: "bar", catAxisOrientation: "maxMin", chartColors: [H.accent3],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisHidden: true,
    showTitle: true, title: "Full-panel model error with field noise on one parameter", titleFontSize: 14,
    titleColor: H.dk1, showLegend: false, barGapWidthPct: 45, objectName: "Noise chart",
  }));
  s.addNotes("Conformal intervals hold their nominal coverage at every level from 50 to 95 percent; raw quantile regression under-covers and GPR is miscalibrated away from 90 percent. Measurement noise matters more than parameter count: a pH error of only 0.1 units raises the full model's error from 0.76 to 3.13, worse than dropping five parameters.");
}

// =================================================================== 12 Sensitivity
{
  const s = slide("CONTENT", "Results");
  title(s, "Which panel works depends on the index definition");
  s.addChart(pres.charts.BAR, [
    { name: "CPCB weights (1/Sᵢ)", labels: ["S3", "S4-routine", "S5", "I3", "S7", "Full-8"], values: [0.957, 0.964, 0.967, 0.977, 0.994, 0.997] },
    { name: "Equal weights", labels: ["S3", "S4-routine", "S5", "I3", "S7", "Full-8"], values: [0.617, 0.902, 0.937, 0.802, 0.990, 0.996] },
  ], chartOpts({
    x: 0.6, y: 1.45, w: 8.0, h: 5.3, barDir: "col", barGrouping: "clustered", chartColors: [H.accent1, H.accent2],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00", valAxisMinVal: 0, valAxisMaxVal: 1.1,
    valAxisMajorUnit: 0.2, valAxisLabelFormatCode: "0.0", showLegend: true, legendPos: "b",
    showTitle: true, title: "R² on unseen stations under two index definitions", titleFontSize: 14, titleColor: H.dk1,
    barGapWidthPct: 60, objectName: "Sensitivity chart",
  }));
  body(s, bullets([
    "Equal weights shift importance to the coliforms (52%) and turbidity (18%)",
    "Uncapped index: S3 R² 0.37, but pH + BOD + turbidity reaches 0.98",
    "EC standard 250–4,000 µS/cm changes ≤ 0.35% of categories",
    "S7 is the only panel robust to every definition",
  ]), { x: 9.0, y: 1.6, w: 3.7, h: 5.1, fontSize: 15, paraSpaceAfter: 10 });
  s.addNotes("A reduced panel inherits the priorities of the index it imitates. Under equal weights S3 explains only 62 percent of the variance; for the uncapped index, which tracks extreme silt and sewage events, turbidity is essential. The EC standard, our least well-sourced value, turns out not to matter.");
}

// =================================================================== 13 Deployment
{
  const s = slide("CONTENT", "Results");
  title(s, "Deployment: first full-panel WQI for 255 stations");
  const st = [["20,132", "visits reconstructed (2018–2021)", C.text2], ["255", "stations that never had a WQI", C.accent1],
    ["3.0", "shift-corrected RMSE (vs 2.9 in CV)", C.text2]];
  st.forEach(([b, l, col], i) => stat(s, 0.6, 1.45 + i * 1.55, 4.0, b, l, col, "Deployment stat " + (i + 1)));
  body(s, [{ text: "Caveat: ", options: { bold: true, color: C.accent3 } },
    { text: "outside 2020, BOD ≤ 1 mg/L is never reported (left blank). Year-to-year trends must account for this reporting floor.", options: {} }],
    { x: 0.6, y: 6.0, w: 5.6, h: 0.9, fontSize: 14 });
  s.addImage({ path: FIG("fig_dep_river_year.png"), x: 6.5, y: 1.35, w: 6.2, h: 6.2 * 1066 / 1312,
    objectName: "River by year heatmap" });
  s.addNotes("We applied the pH-DO-BOD model to every visit lacking a full panel. An adversarial check shows the inputs differ mainly in BOD; reweighting the CV errors for that shift gives RMSE 3.0, so accuracy barely changes. The data also revealed that low BOD values are left blank outside 2020, which would otherwise look like a trend.");
}

// =================================================================== 14 Recommendation
{
  const s = slide("CONTENT", "Recommendation");
  title(s, "Recommended monitoring kit");
  const hdr = () => ({ bold: true, color: C.background1, fill: { color: C.text2 }, fontSize: 14 });
  const rows = [
    ["Tier", "Parameters", "R²", "Category acc.", "90% interval"].map((t) => ({ text: t, options: hdr() })),
    ["0  Routine (no new cost)", "pH, DO, BOD, fecal coliform + location, month", "0.977", "93.9%", "± 3.6"],
    ["1  + turbidity probe", "pH, DO, BOD, turbidity", "0.994", "96.8%", "± 1.6"],
    ["2  + nitrate field kit", "pH, DO, BOD, turbidity, nitrate-N", "0.998", "97.7%", "± 1.1"],
    ["Public-health robust", "S7: + both coliforms, EC", "0.994", "97.0%", "± 1.5"],
    ["Screening only", "pH, DO, EC, turbidity (all probes)", "0.828", "82.4%", "± 9.8"],
  ].map((r, i) => i === 0 ? r : r.map((c, j) => ({ text: c, options: {
    bold: j === 0, color: C.text1, fontSize: 14, fill: { color: i % 2 ? C.background1 : C.background2 } } })));
  s.addTable(rows, { x: 0.6, y: 1.45, w: 12.1, colW: [2.9, 4.6, 1.2, 1.8, 1.6], rowH: 0.52,
    border: { type: "solid", pt: 0.5, color: "D9E2E6" }, valign: "middle", margin: [0.04, 0.1, 0.04, 0.1],
    objectName: "Kit table" });
  const rules = ["Calibrate pH to ±0.05 and quality-control BOD", "Route to a dedicated model for whatever was measured",
    "Publish the conformal interval with every estimate", "Report fecal coliform exceedance alongside the WQI"];
  rules.forEach((t, i) => {
    const x = 0.6 + (i % 2) * 6.15;
    const y = 4.9 + Math.floor(i / 2) * 0.95;
    badge(s, x, y + 0.1, i + 1, "Rule " + (i + 1));
    s.addText(t, { x: x + 0.6, y, w: 5.4, h: 0.65, fontSize: 15, color: C.text1, margin: 0, valign: "middle",
      isTextBox: true, objectName: "Rule " + (i + 1) + " text" });
  });
  s.addNotes("Tier 0 needs nothing new: the routine panel plus location and month already gives R-squared 0.977. A single turbidity probe brings it to 0.994. The operating rules matter as much as the parameters: pH calibration, routing to the right model instead of imputing, publishing intervals, and reporting coliforms separately because the CPCB weighting ignores them.");
}

// =================================================================== 15 Conclusion
{
  const s = slide("DARK", "Recommendation");
  s.addText("Answer: yes, with the right three parameters", { x: 0.7, y: 0.6, w: 12, h: 0.9, fontSize: 34, bold: true,
    color: C.background1, fontFace: THEME.headFontFace, margin: 0, isTextBox: true, objectName: "Conclusion title" });
  const take = [
    ["pH, DO and BOD reproduce the CPCB WQI", "R² 0.957 and 91% category accuracy at unseen stations; 0.994 with a turbidity probe"],
    ["Learning beats re-weighting", "once data from about 25 stations are available, with calibrated ±4.7-point intervals"],
    ["Mind the index and the instruments", "the CPCB weights ignore coliforms, and pH precision matters more than parameter count"],
  ];
  take.forEach(([h, d], i) => {
    const y = 1.85 + i * 1.3;
    s.addShape(pres.shapes.OVAL, { x: 0.7, y: y + 0.1, w: 0.55, h: 0.55, fill: { color: C.accent2 },
      line: { color: C.accent2 }, objectName: "Takeaway badge " + (i + 1) });
    s.addText(String(i + 1), { x: 0.7, y: y + 0.1, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: C.text2,
      align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "Takeaway number " + (i + 1) });
    s.addText([{ text: h, options: { bold: true, breakLine: true, fontSize: 20 } }, { text: d, options: { fontSize: 15, color: C.background2 } }],
      { x: 1.5, y, w: 11.1, h: 1.1, color: C.background1, margin: 0, valign: "top", isTextBox: true,
        objectName: "Takeaway " + (i + 1) });
  });
  s.addText([{ text: "Next: ", options: { bold: true, color: C.accent2 } },
    { text: "more full-panel years, censored-BOD handling, NSF/CCME indices, satellite turbidity, a field tool.", options: {} }],
    { x: 0.7, y: 5.95, w: 12, h: 0.5, fontSize: 15, color: C.background1, margin: 0, isTextBox: true, objectName: "Next steps" });
  s.addText("Thank you. Questions?", { x: 0.7, y: 6.6, w: 12, h: 0.5, fontSize: 18, italic: true, color: C.accent2,
    margin: 0, isTextBox: true, objectName: "Thanks" });
  s.addNotes("Summarise: reduced-parameter monitoring works for the CPCB index if the right parameters are measured precisely and the model has enough stations to learn from. Close with the caveats and next steps, then take questions.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  if (APPLY_THEME) {
    const { applyTheme } = require(APPLY_THEME);
    await applyTheme(OUT, THEME);
  }
  console.log("wrote " + OUT);
})();
