import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(scriptDir, "..");
// The committed sample images are the single source of truth. This script only
// reads them — it never touches the gitignored data/ folder.
const sampleRoot = path.join(frontendRoot, "public", "sample_labels");
const outPath = path.join(frontendRoot, "src", "generated", "sampleLabels.ts");

const metadata = {
  "pass/3_steves_winery_2013-08-11.png": {
    brand: "3 Steves Winery",
    desc: "Expected pass: domestic wine with table-wine alcohol-content omission treated as not required.",
    applicationValues: {
      brand_name: "3 Steves Winery",
      beverage_class: "wine",
      class_type_designation: "Table Wine",
      alcohol_content: "",
      net_contents: "750 ml",
      name_address: "Bottled By 3 Steves Winery, Livermore, CA",
      country_of_origin: "Domestic",
    },
  },
  "pass/3_steves_winery_2017-05-25.png": {
    brand: "3 Steves Reserve",
    desc: "Expected pass: application values match the 2014 Cabernet Sauvignon label.",
    applicationValues: {
      brand_name: "3 Steves Reserve",
      beverage_class: "wine",
      class_type_designation: "Cabernet Sauvignon",
      alcohol_content: "Alcohol: 14.6% by volume",
      net_contents: "750 ml",
      name_address:
        "Grown, Produced and Bottled by 3 Steves Winery, Livermore Valley, California",
      country_of_origin: "Domestic",
    },
  },
  "pass/3_steves_winery_2017-05-25_glare.png": {
    brand: "3 Steves Reserve",
    desc: "Expected pass: intentionally strong glare, but the required label information remains readable.",
    applicationValues: {
      brand_name: "3 Steves Reserve",
      beverage_class: "wine",
      class_type_designation: "Cabernet Sauvignon",
      alcohol_content: "Alcohol: 14.6% by volume",
      net_contents: "750 ml",
      name_address:
        "Grown, Produced and Bottled by 3 Steves Winery, Livermore Valley, California",
      country_of_origin: "Domestic",
    },
  },
  "pass/3_steves_winery_2018-12-18.png": {
    brand: "3 Steves Winery",
    desc: "Expected pass: application values match the 2018 Fume Blanc label.",
    applicationValues: {
      brand_name: "3 Steves Winery",
      beverage_class: "wine",
      class_type_designation: "Fume Blanc",
      alcohol_content: "Alc. 13.2% by Volume",
      net_contents: "750 ml",
      name_address: "Bottled By 3 Steves Winery, Livermore, CA",
      country_of_origin: "Domestic",
    },
  },
  "pass/altos_2017-10-25.png": {
    brand: "Altos de Inurrieta",
    desc: "Expected pass: imported wine where application origin status is Imported and the label shows Spain.",
    applicationValues: {
      brand_name: "Altos de Inurrieta",
      beverage_class: "wine",
      class_type_designation: "Red Wine",
      alcohol_content: "Alc. 14.5% by Vol.",
      net_contents: "750 ml",
      name_address: "Imported by GV Berkeley LLC, Berkeley, California",
      country_of_origin: "Spain",
    },
  },
  "pass/altos_2017-10-25_rotated.png": {
    brand: "Altos de Inurrieta",
    desc: "Expected pass: intentionally 90-degree rotated photo, but all required label information remains visible.",
    applicationValues: {
      brand_name: "Altos de Inurrieta",
      beverage_class: "wine",
      class_type_designation: "Red Wine",
      alcohol_content: "Alc. 14.5% by Vol.",
      net_contents: "750 ml",
      name_address: "Imported by GV Berkeley LLC, Berkeley, California",
      country_of_origin: "Spain",
    },
  },
  "pass/apple_brandy_2016-11-02.png": {
    brand: "Dampfwerk Apple Brandy",
    desc: "Expected pass: application values match the Dampfwerk Apple Brandy label.",
    applicationValues: {
      brand_name: "Dampfwerk Apple Brandy",
      beverage_class: "spirits",
      class_type_designation: "Apple Brandy",
      alcohol_content: "43% Alc. by Vol.",
      net_contents: "375 ml",
      name_address: "Distilled and bottled by Dampfwerk Distilling, St Louis Park, MN 55416",
      country_of_origin: "Domestic",
    },
  },
  "pass/apple_brandy_2016-11-02_rotated.png": {
    brand: "Dampfwerk Apple Brandy",
    desc: "Expected pass: intentionally upside-down photo, but all required label information remains visible.",
    applicationValues: {
      brand_name: "Dampfwerk Apple Brandy",
      beverage_class: "spirits",
      class_type_designation: "Apple Brandy",
      alcohol_content: "43% Alc. by Vol.",
      net_contents: "375 ml",
      name_address: "Distilled and bottled by Dampfwerk Distilling, St Louis Park, MN 55416",
      country_of_origin: "Domestic",
    },
  },
  "pass/azienda_agricola_cipriana_2018-11-07_18309001000239.png": {
    brand: "San Martino",
    desc: "Expected pass: application values match the imported Bolgheri Superiore label.",
    applicationValues: {
      brand_name: "San Martino",
      beverage_class: "wine",
      class_type_designation: "Bolgheri Superiore Red Wine",
      alcohol_content: "Alc. 14.5% by vol.",
      net_contents: "Net cont. 750 ml",
      name_address:
        "Bottled by Societa Agricola Cipriana S.R.L., Spirano - Italia; Imported by Buta - Distributors Inc., Boca Raton, FL",
      country_of_origin: "Italy",
    },
  },
  "pass/barenjager_2011-03-09_11038001000727.png": {
    brand: "Barenjager",
    desc: "Expected pass: application values match the imported honey liqueur label.",
    applicationValues: {
      brand_name: "Barenjager",
      beverage_class: "spirits",
      class_type_designation: "Honey Liqueur",
      alcohol_content: "35% Alc. by Vol.",
      net_contents: "50 ml",
      name_address:
        "Imported by Sidney Frank Importing Co., Inc., New Rochelle, NY; produced and bottled in Germany",
      country_of_origin: "Germany",
    },
  },
  "pass/barenjager_2011-06-28.png": {
    brand: "Barenjager",
    desc: "Expected pass: application values match the honey and bourbon label.",
    applicationValues: {
      brand_name: "Barenjager",
      beverage_class: "spirits",
      class_type_designation: "Honey Liqueur and Bourbon Whiskey",
      alcohol_content: "35% alc/vol",
      net_contents: "50 ml",
      name_address:
        "Imported by Sidney Frank Importing Co. Inc., New Rochelle, N.Y.; produced & bottled in Germany",
      country_of_origin: "Germany",
    },
  },
  "pass/blazic_2019-08-19.png": {
    brand: "Blazic",
    desc: "Expected pass: application values match the imported Collio Ribolla Gialla label.",
    applicationValues: {
      brand_name: "Blazic",
      beverage_class: "wine",
      class_type_designation: "Collio Ribolla Gialla White Wine",
      alcohol_content: "Alc. 12.5% by vol.",
      net_contents: "750 ml content",
      name_address:
        "Produced and bottled by Blazic S. Agr. S., Localita Zegla, 16 - 34071 Cormons (GO) - Italy; Imported by Buta Distributors Inc., Delray Beach, FL",
      country_of_origin: "Italy",
    },
  },
  "pass/blazic_2019-08-19_19213001000687.png": {
    brand: "Blazic",
    desc: "Expected pass: application values match the imported Collio Friulano label.",
    applicationValues: {
      brand_name: "Blazic",
      beverage_class: "wine",
      class_type_designation: "Collio Friulano White Wine",
      alcohol_content: "Alc. 13.5% by vol.",
      net_contents: "750 ml content",
      name_address:
        "Produced and bottled by Blazic S. Agr. S., Localita Zegla, 16 - 34071 Cormons (GO) - Italy; Imported by Buta Distributors Inc., Delray Beach, FL",
      country_of_origin: "Italy",
    },
  },
  "pass/blue_ridge_winery_llc_2018-08-24.png": {
    brand: "Blue Ridge",
    desc: "Expected pass: application values match the Blue Ridge Inspiration label.",
    applicationValues: {
      brand_name: "Blue Ridge",
      beverage_class: "wine",
      class_type_designation: "White grape wine with artificial flavor",
      alcohol_content: "Alc. 11% by vol.",
      net_contents: "750 ml",
      name_address:
        "Vinted and bottled by Blue Ridge Winery, LLC, 239 Blue Ridge Road, Saylorsburg, PA 18353",
      country_of_origin: "Domestic",
    },
  },
  "pass/blue_ridge_winery_llc_2018-08-24_glare.png": {
    brand: "Blue Ridge",
    desc: "Expected pass: intentionally strong glare, but the required label information remains readable.",
    applicationValues: {
      brand_name: "Blue Ridge",
      beverage_class: "wine",
      class_type_designation: "White grape wine with artificial flavor",
      alcohol_content: "Alc. 11% by vol.",
      net_contents: "750 ml",
      name_address:
        "Vinted and bottled by Blue Ridge Winery, LLC, 239 Blue Ridge Road, Saylorsburg, PA 18353",
      country_of_origin: "Domestic",
    },
  },
  "pass/bluebird_distilling_2015-09-02.png": {
    brand: "Bluebird Distilling",
    desc: "Expected pass: application values match the Four Grain Bourbon Whiskey label.",
    applicationValues: {
      brand_name: "Bluebird Distilling",
      beverage_class: "spirits",
      class_type_designation: "Four Grain Bourbon Whiskey",
      alcohol_content: "46% Alc/Vol",
      net_contents: "750 ml",
      name_address: "Distilled & bottled by Bluebird Distilling, Phoenixville, PA",
      country_of_origin: "Domestic",
    },
  },
  "fail/brook_and_bull_2018-01-10.png": {
    brand: "Brook & Bull",
    desc: "Expected fail: net contents are not present on the label.",
    applicationValues: {
      brand_name: "Brook & Bull",
      beverage_class: "wine",
      class_type_designation: "52% Cabernet Sauvignon 48% Malbec",
      alcohol_content: "Alc. 14.5% by vol.",
      net_contents: "750 ml",
      name_address: "Bottled by Brook & Bull, Walla Walla, WA",
      country_of_origin: "Domestic",
    },
  },

  "fail/cantine_mothia_2018-12-06.png": failMetadata(
    "Cantine Mothia",
    "Expected fail: application brand, net contents, and domestic/imported status are intentionally wrong.",
    {
      brand_name: "Cantina Monteluna",
      beverage_class: "wine",
      class_type_designation: "Pinot Grigio",
      alcohol_content: "11% by vol.",
      net_contents: "1 L",
      name_address: "Imported by Example Imports, Miami, FL",
      country_of_origin: "Domestic",
    },
  ),
  "fail/ca_piadera_2018-05-15.png": failMetadata(
    "Ca' Piadera",
    "Expected fail: application class/type and alcohol content are intentionally wrong.",
    {
      brand_name: "Ca' Piadera",
      beverage_class: "wine",
      class_type_designation: "Sweet Red Wine",
      alcohol_content: "14.5% by vol.",
      net_contents: "750 ml",
      name_address: "Bottled by Az. Ag. Ca Piadera S.S., Tarzo (TV), Italy",
      country_of_origin: "Italy",
    },
  ),
  "fail/cold_spring_brewery_2019-12-20.png": failMetadata(
    "Cold Spring Brewery",
    "Expected fail: domestic malt label is submitted as Canada while alcohol content is federally optional.",
    {
      brand_name: "Cold Spring Brewery",
      beverage_class: "malt",
      class_type_designation: "Malt Beverage",
      alcohol_content: "",
      net_contents: "750 ml",
      name_address: "Brewed by Cold Spring Brewery, Cold Spring, MN",
      country_of_origin: "Canada",
    },
  ),
  "fail/duck_walk_vineyards_2014-10-15_14275001000239.png": failMetadata(
    "Duck Walk Vineyards",
    "Expected fail: application varietal and alcohol content are intentionally wrong.",
    {
      brand_name: "Duck Walk Vineyards",
      beverage_class: "wine",
      class_type_designation: "Merlot",
      alcohol_content: "14.5% by vol.",
      net_contents: "375 ml",
      name_address: "Produced and bottled by Duck Walk Vineyards, Water Mill, NY",
      country_of_origin: "Domestic",
    },
  ),
  "fail/duck_walk_vineyards_2015-05-14.png": failMetadata(
    "Duck Walk Vineyards",
    "Expected fail: application type is intentionally wrong for the rose label.",
    {
      brand_name: "Duck Walk Vineyards",
      beverage_class: "wine",
      class_type_designation: "Chardonnay",
      alcohol_content: "12.5% alc/vol",
      net_contents: "750 ml",
      name_address: "Produced and bottled by Duck Walk Vineyards, Water Mill, NY",
      country_of_origin: "Domestic",
    },
  ),
  "fail/duck_walk_vineyards_2015-05-14_15113001000558.png": failMetadata(
    "Duck Walk Vineyards",
    "Expected fail: application brand and class/type are intentionally wrong.",
    {
      brand_name: "Duck Creek Cellars",
      beverage_class: "wine",
      class_type_designation: "Cabernet Sauvignon",
      alcohol_content: "13.0% alc/vol",
      net_contents: "750 ml",
      name_address: "Produced and bottled by Duck Walk Vineyards, Water Mill, NY",
      country_of_origin: "Domestic",
    },
  ),
  "fail/etim_l_esparver_2015-03-26.png": failMetadata(
    "Etim L'Esparver",
    "Expected fail: imported label has missing application origin status and wrong alcohol content.",
    {
      brand_name: "Etim L'Esparver",
      beverage_class: "wine",
      class_type_designation: "White Wine",
      alcohol_content: "11.0% alc/vol",
      net_contents: "750 ml",
      name_address: "Imported by Opici Imports Co., Glen Rock, NJ",
      country_of_origin: "",
    },
  ),
  "fail/gekkeikan_2013-01-04.png": failMetadata(
    "Gekkeikan",
    "Expected fail: application class/type and alcohol content are intentionally wrong.",
    {
      brand_name: "Gekkeikan",
      beverage_class: "wine",
      class_type_designation: "Dry Gin",
      alcohol_content: "40% alc/vol",
      net_contents: "720 ml",
      name_address:
        "Produced by Gekkeikan Sake Company, Ltd.; Imported by Sidney Frank Importing Co., Inc., New Rochelle, NY",
      country_of_origin: "Domestic",
    },
  ),
  "fail/good_people_brewing_company_2016-08-12.png": failMetadata(
    "Good People Brewing Company",
    "Expected fail: malt label uses optional blank ABV, but the application says Canada for a domestic label.",
    {
      brand_name: "Good People Brewing Company",
      beverage_class: "malt",
      class_type_designation: "Ale",
      alcohol_content: "",
      net_contents: "12 fl oz",
      name_address: "Bottled by Good People Brewing Company, Birmingham, AL",
      country_of_origin: "Canada",
    },
  ),

  "fail/blue_ridge_winery_llc_2018-08-29_attorney_general_warning.png": {
    brand: "Blue Ridge Princess",
    desc: "Expected fail: the government warning text was changed from Surgeon General to Attorney General.",
    applicationValues: {
      brand_name: "Blue Ridge Princess",
      beverage_class: "wine",
      class_type_designation: "Rose grape wine with artificial color",
      alcohol_content: "Alc. 12% by vol.",
      net_contents: "750 ml",
      name_address:
        "Vinted and bottled by Blue Ridge Winery, LLC, 239 Blue Ridge Road, Saylorsburg, PA 18353",
      country_of_origin: "Domestic",
    },
  },
  "fail/cantine_mothia_2018-11-15_warning_covered.png": {
    brand: "Dedicato a Francesco",
    desc: "Expected fail: the government warning block was visibly covered.",
    applicationValues: {
      brand_name: "Dedicato a Francesco",
      beverage_class: "wine",
      class_type_designation: "Terre Siciliane I.G.P. Nero d'Avola Red Wine",
      alcohol_content: "Alc. 14.5% by vol.",
      net_contents: "Net contents 750 ml",
      name_address:
        "Product and bottled by Cantine Mothia S.r.l., Marsala (Italia); Imported by Buta Distributors Inc., Boca Raton (FL)",
      country_of_origin: "Italy",
    },
  },
  "fail/chaglasian_winery_and_vineyards_2019-05-14_19120001000487_warning_removed.png": {
    brand: "Areni",
    desc: "Expected fail: the government warning block was removed from the back label.",
    applicationValues: {
      brand_name: "Areni",
      beverage_class: "wine",
      class_type_designation: "Tempranillo Red Wine",
      alcohol_content: "Alc. 16.5% by vol.",
      net_contents: "Net cont. 750 ml",
      name_address:
        "Imported by Justabout Winery LLC, Venetia, PA, USA; Estate grown and bottled by Chaglasian Winery & Vineyards, San Rafael, Mendoza",
      country_of_origin: "Argentina",
    },
  },
  "fail/cleo_2019-04-17_lowercase_warning.png": {
    brand: "Cleo",
    desc: "Expected fail: the government warning heading was changed to lowercase.",
    applicationValues: {
      brand_name: "Cleo",
      beverage_class: "spirits",
      class_type_designation: "Gin",
      alcohol_content: "40% Alc/Vol",
      net_contents: "750 ml",
      name_address: "Distilled and bottled by Black Market Spirits, Santa Barbara, CA",
      country_of_origin: "Domestic",
    },
  },
  "fail/gekkeikan_2014-09-11_mixedcase_warning.png": {
    brand: "Gekkeikan Gold",
    desc: "Expected fail: the government warning heading was changed to mixed case.",
    applicationValues: {
      brand_name: "Gekkeikan Gold",
      beverage_class: "wine",
      class_type_designation: "Junmai Sake",
      alcohol_content: "16.5% Alc./Vol.",
      net_contents: "720 ml",
      name_address:
        "Produced by Gekkeikan Sake Company, Ltd.; Imported by Sidney Frank Importing Co., Inc., New Rochelle, NY",
      country_of_origin: "Japan",
    },
  },
  "fail/karnobatska_2018-08-20_blurry_warning.png": {
    brand: "Karnobatska",
    desc: "Expected fail: the government warning text was made too blurry to reliably verify.",
    applicationValues: {
      brand_name: "Karnobatska",
      beverage_class: "spirits",
      class_type_designation: "Special Grape Brandy",
      alcohol_content: "Alc. 40% by vol.",
      net_contents: "1 L",
      name_address:
        "Produced and bottled by SIS Industries OOD, Bulgaria; Imported by Malinka Imports LLC, Palatine, IL 60067",
      country_of_origin: "Bulgaria",
    },
  },
};

const categories = ["pass", "fail"];
const imageExtensions = new Set([".png", ".jpg", ".jpeg", ".webp"]);

const missingMetadata = [];

const samples = categories.flatMap((category) => {
  const dir = path.join(sampleRoot, category);
  if (!existsSync(dir)) return [];

  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && imageExtensions.has(path.extname(entry.name).toLowerCase()))
    .map((entry) => `${category}/${entry.name}`)
    .sort((a, b) => a.localeCompare(b))
    .map((file) => {
      const entryMetadata = metadata[file];
      if (!hasRequiredMetadata(entryMetadata)) {
        missingMetadata.push(file);
      }
      return {
        id: `${category}-${slugify(path.basename(file, path.extname(file)))}`,
        brand: entryMetadata?.brand ?? titleize(path.basename(file, path.extname(file))),
        file,
        desc: entryMetadata?.desc ?? `Missing curated sample summary for ${file}.`,
        applicationValues: entryMetadata?.applicationValues ?? emptyApplicationValues(),
      };
    });
});

if (missingMetadata.length > 0) {
  throw new Error(
    `Missing sample metadata for:\n${missingMetadata.map((file) => `- ${file}`).join("\n")}`,
  );
}

const ids = new Set();
for (const sample of samples) {
  if (ids.has(sample.id)) {
    throw new Error(`Duplicate generated sample id: ${sample.id}`);
  }
  ids.add(sample.id);
}

const source = `// This file is generated by scripts/generate-sample-labels.mjs.
// Do not edit by hand; update public/sample_labels or the script metadata instead.

export interface SampleApplicationValues {
  brand_name: string;
  beverage_class: "spirits" | "wine" | "malt";
  class_type_designation: string;
  alcohol_content: string;
  net_contents: string;
  name_address: string;
  country_of_origin: string;
  malt_added_nonbeverage_alcohol?: boolean;
  malt_color_additive_applicable?: boolean;
}

export interface SampleEntry {
  id: string;
  brand: string;
  file: string;
  desc: string;
  applicationValues: SampleApplicationValues;
}

export const SAMPLES: SampleEntry[] = ${JSON.stringify(samples, null, 2)};
`;

mkdirSync(path.dirname(outPath), { recursive: true });
writeFileSync(outPath, source, "utf8");
console.log(`Generated ${samples.length} sample label entries.`);

function hasRequiredMetadata(entry) {
  if (!entry?.brand || !entry?.desc) {
    return false;
  }
  const values = entry.applicationValues;
  return (
    values?.brand_name &&
    values?.beverage_class &&
    values?.class_type_designation &&
    values?.net_contents &&
    values?.name_address &&
    hasOwnString(values, "alcohol_content") &&
    hasOwnString(values, "country_of_origin")
  );
}

function hasOwnString(values, key) {
  return Object.hasOwn(values ?? {}, key) && typeof values[key] === "string";
}

function emptyApplicationValues() {
  return {
    brand_name: "",
    beverage_class: "wine",
    class_type_designation: "",
    alcohol_content: "",
    net_contents: "",
    name_address: "",
    country_of_origin: "",
  };
}

function failMetadata(brand, desc, applicationValues) {
  return { brand, desc, applicationValues };
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function titleize(value) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
