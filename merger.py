import json
import os
import re
from collections import defaultdict, OrderedDict
from tabulate import tabulate

DATA_DIR = "data"
FILES = ["hoyts.json", "event.json", "village.json"]
OUTPUT_FILE = os.path.join(DATA_DIR, "australia.json")

def parse_movie_and_language(raw_name):
    """
    Extracts the base movie name and the language suffix.
    Returns (normalized_name, language)
    """
    if not raw_name:
        return "Unknown", "Unknown"
    
    match = re.search(r'[\(\[](.*?)[\)\]]', raw_name)
    language = "English"
    if match:
        extracted = match.group(1).strip()
        if len(extracted.split()) <= 2:
            language = extracted
    
    norm_name = re.sub(r'[\(\[].*?[\)\]]', '', raw_name)
    norm_name = " ".join(norm_name.split())
    return norm_name, language

def load_data():
    all_data = []
    for filename in FILES:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                all_data.append(json.load(f))
        except Exception as e:
            print(f"Error loading {path}: {e}")
    return all_data

def create_summary_item():
    return {"shows": 0, "totalSeats": 0, "soldSeats": 0, "gross": 0.0, "occupancy": "0%"}

def update_summary(sum_obj, show):
    sum_obj["shows"] += 1
    sum_obj["totalSeats"] += show.get("totalSeats", 0)
    sum_obj["soldSeats"] += show.get("soldSeats", 0)
    sum_obj["gross"] += show.get("gross", 0.0)

def finalize_summary(sum_obj):
    if sum_obj["totalSeats"] > 0:
        occ = (sum_obj["soldSeats"] / sum_obj["totalSeats"]) * 100
    else:
        occ = 0
    sum_obj["occupancy"] = f"{round(occ, 2)}%"
    sum_obj["gross"] = round(sum_obj["gross"], 2)

def main():
    raw_datasets = load_data()
    if not raw_datasets:
        print("No data found to merge.")
        return

    # Deep nested structure for aggregation
    raw_merged = defaultdict(lambda: defaultdict(lambda: {
        "summary": create_summary_item(),
        "languages": defaultdict(create_summary_item),
        "sources": defaultdict(create_summary_item),
        "shows": []
    }))

    for dataset in raw_datasets:
        for movie_id, movie_data in dataset.items():
            raw_name = movie_data.get("movieName", "Unknown")
            norm_name, language = parse_movie_and_language(raw_name)

            for date_key, date_data in movie_data.items():
                if date_key == "movieName":
                    continue
                
                shows = date_data.get("shows", [])
                m_date = raw_merged[norm_name][date_key]
                
                for show in shows:
                    source = show.get("Source", "Unknown")
                    full_show = show.copy()
                    full_show["Language"] = language
                    m_date["shows"].append(full_show)
                    
                    update_summary(m_date["summary"], show)
                    update_summary(m_date["languages"][language], show)
                    update_summary(m_date["sources"][source], show)

    # Finalize all summaries AND construct sorted structure for JSON
    # Structure: movie_name -> { "movieName": ..., "dates": { YYYY-MM-DD: { summary, languages, sources, shows } } }
    final_json = OrderedDict()
    
    for movie_name in sorted(raw_merged.keys()):
        final_json[movie_name] = OrderedDict([("movieName", movie_name)])
        for date_key in sorted(raw_merged[movie_name].keys()):
            d_data = raw_merged[movie_name][date_key]
            
            finalize_summary(d_data["summary"])
            for l_sum in d_data["languages"].values(): finalize_summary(l_sum)
            for s_sum in d_data["sources"].values(): finalize_summary(s_sum)
            
            final_json[movie_name][date_key] = d_data

    # Save to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2)
    print(f"Successfully saved merged data to {OUTPUT_FILE}")

    # -------- CONSOLE TABLE RENDERING --------
    print("\n" + "=" * 105)
    print("🌍 AUSTRALIA COMPREHENSIVE BOX OFFICE SUMMARY")
    print("=" * 105)

    grand_total = create_summary_item()
    overall_date_agg = defaultdict(create_summary_item)

    # Pre-calculate overall date-wise for the top table
    for movie_name, dates in final_json.items():
        for date_key, d_data in dates.items():
            if date_key == "movieName": continue
            s = d_data["summary"]
            # Grand Totals
            grand_total["shows"] += s["shows"]
            grand_total["totalSeats"] += s["totalSeats"]
            grand_total["soldSeats"] += s["soldSeats"]
            grand_total["gross"] += s["gross"]
            # Overall Date-wise
            d_agg = overall_date_agg[date_key]
            d_agg["shows"] += s["shows"]
            d_agg["totalSeats"] += s["totalSeats"]
            d_agg["soldSeats"] += s["soldSeats"]
            d_agg["gross"] += s["gross"]

    # 1. Overall DATE-WISE TOTALS (TOP)
    print("\n📅 OVERALL PERFORMANCE BY DATE (ALL MOVIES)")
    overall_date_table = []
    for d in sorted(overall_date_agg.keys()):
        s = overall_date_agg[d]
        finalize_summary(s)
        overall_date_table.append([d, s["shows"], s["totalSeats"], s["soldSeats"], s["occupancy"], f"${s['gross']:,}"])
    print(tabulate(overall_date_table, headers=["Date", "Shows", "Total Seats", "Sold", "Occ %", "Gross ($)"], tablefmt="pretty"))

    # 2. Movie-wise Breakdown
    for movie_name, dates in final_json.items():
        print(f"\n🎬 {movie_name.upper()}")
        
        date_table = []
        lang_total = defaultdict(create_summary_item)
        src_total = defaultdict(create_summary_item)

        for d in sorted(dates.keys()):
            if d == "movieName": continue
            s = dates[d]["summary"]
            date_table.append([d, s["shows"], s["totalSeats"], s["soldSeats"], s["occupancy"], f"${s['gross']:,}"])
            
            # Aggregate totals for inline breakdown
            for lang, l_sum in dates[d]["languages"].items():
                lang_total[lang]["shows"] += l_sum["shows"]
                lang_total[lang]["totalSeats"] += l_sum["totalSeats"]
                lang_total[lang]["soldSeats"] += l_sum["soldSeats"]
                lang_total[lang]["gross"] += l_sum["gross"]
            for src, src_sum in dates[d]["sources"].items():
                src_total[src]["shows"] += src_sum["shows"]
                src_total[src]["totalSeats"] += src_sum["totalSeats"]
                src_total[src]["soldSeats"] += src_sum["soldSeats"]
                src_total[src]["gross"] += src_sum["gross"]

        print(tabulate(date_table, headers=["Date", "Shows", "Total Seats", "Sold", "Occ %", "Gross ($)"], tablefmt="pretty"))
        
        # Inline Language Summary
        lang_bits = []
        for l, ls in lang_total.items():
            finalize_summary(ls)
            lang_bits.append(f"{l}: ${ls['gross']:,}")
        print(f"   ∟ Languages: {', '.join(lang_bits)}")

        # Inline Source Summary
        src_bits = []
        for src, ss in src_total.items():
            finalize_summary(ss)
            src_bits.append(f"{src}: ${ss['gross']:,}")
        print(f"   ∟ Sources:   {', '.join(src_bits)}")
        print("-" * 105)

    # Final Grand Total
    finalize_summary(grand_total)
    print("\n🏆 GRAND TOTAL (AUSTRALIA)")
    print(tabulate(
        [[grand_total["shows"], grand_total["totalSeats"], grand_total["soldSeats"], grand_total["occupancy"], f"${grand_total['gross']:,}"]],
        headers=["Shows", "Total Seats", "Sold", "Occ %", "Gross ($)"],
        tablefmt="pretty"
    ))
    print("=" * 105)

if __name__ == "__main__":
    main()
