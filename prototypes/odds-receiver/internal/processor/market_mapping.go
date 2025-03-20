// internal/processor/market_mapping.go
package processor

import "fmt"

// This file contains mappings and descriptions for market types, scopes, and subtypes
// Based on the Enetpulse documentation

// GetMarketTypeInfo returns the name and description for a market type ID
func GetMarketTypeInfo(typeFK int) (string, string) {
	marketTypes := map[int]struct{ Name, Description string }{
		1:  {"1x2", "1x2 - 3Way - Home/Draw/Away"},
		2:  {"12", "12 - 2Way - Home/Away"},
		3:  {"oe", "Odd/Even"},
		4:  {"ou", "Over/Under"},
		5:  {"cs", "Correct Score"},
		6:  {"ah", "Asian Handicap"},
		7:  {"c_ah", "Corner Asian Handicap"},
		8:  {"1x2_hc", "3Way Handicap"},
		9:  {"win", "Winner"},
		10: {"dc", "Double Chance"},
		11: {"gs", "Goalscorer"},
		12: {"ht_ft", "Half Time / Full Time"},
		13: {"ng", "Number of Goals"},
		14: {"smg", "Half with Most Goals"},
		15: {"tng", "Time of Next Goal"},
		16: {"nc", "Next Corner"},
		17: {"dnb", "Draw No Bet"},
		18: {"bts", "Both to Score"},
		19: {"wtn", "Win to Nil"},
		20: {"g_ah", "Game Handicap"},
		21: {"s_ah", "Set Handicap"},
		22: {"p_ou", "Points Over/Under"},
		23: {"yc_ou", "Yellow Cards Over/Under"},
		24: {"b_first", "First Team Booking"},
		25: {"b_most", "Most Booking"},
		26: {"b_nb", "Number of Cards"},
		27: {"c_oe", "Corners Odd/Even"},
		28: {"c_hc", "Corner Handicap"},
		29: {"c_ou", "Corners Over/Under"},
		30: {"c_last", "Last Corner"},
		31: {"c_most", "Most Corners"},
		32: {"c_nb", "Number of Corners"},
		33: {"c_sm", "Half with Most Corners"},
		34: {"c_par_nb", "Team Number of Corners"},
		35: {"par_ou", "Team Score Over/Under"},
		36: {"par_oe", "Team Odd/Even Goals"},
		37: {"par_ts", "Team Total Score"},
		38: {"p_hc", "Points Handicap"},
		39: {"ew", "Each Way"},
		40: {"s_first", "First Team To Score"},
		41: {"s_ou", "Sets Over/Under"},
		42: {"tb", "Tiebreak"},
		43: {"s_next", "Next Team to Score"},
		44: {"toq", "To Qualify"},
		45: {"car_ou", "Total Cards Over/Under"},
	}

	if info, ok := marketTypes[typeFK]; ok {
		return info.Name, info.Description
	}
	return "unknown", "Unknown market type"
}

// GetMarketSubtypeInfo returns the name and description for a market subtype ID
func GetMarketSubtypeInfo(subtypeFK int) (string, string) {
	marketSubtypes := map[int]struct{ Name, Description string }{
		1:  {"win", "Win"},
		2:  {"draw", "Draw"},
		3:  {"over", "Over"},
		4:  {"under", "Under"},
		5:  {"odd", "Odd"},
		6:  {"even", "Even"},
		7:  {"win_draw", "Win/Draw"},
		8:  {"score", "Score"},
		9:  {"next", "Next"},
		10: {"yes", "Yes"},
		11: {"no", "No"},
		12: {"from", "From"},
		13: {"from_to", "From To"},
		14: {"winner_of_tournament", "Winner of Tournament"},
		15: {"winner_of_stage", "Winner of Stage"},
		16: {"winner_of_event", "Winner of Event"},
		17: {"topscorer_of_tournament", "Top Scorer of Tournament"},
		18: {"topscorer_of_stage", "Top Scorer of Stage"},
		19: {"topx_of_tournament", "Top X of Tournament"},
		20: {"topx_of_stage", "Top X of Stage"},
		21: {"relegation_from_stage", "Relegation from Stage"},
		22: {"topx_of_event", "Top X of Event"},
		23: {"to", "To"},
		24: {"none", "None"},
		25: {"place", "Place"},
		26: {"last", "Last"},
		27: {"anytime", "Anytime"},
	}

	if info, ok := marketSubtypes[subtypeFK]; ok {
		return info.Name, info.Description
	}
	return "unknown", "Unknown market subtype"
}

// GetMarketScopeInfo returns the name and description for a market scope ID
func GetMarketScopeInfo(scopeFK int) (string, string) {
	marketScopes := map[int]struct{ Name, Description string }{
		1:  {"ord", "Ordinary time"},
		2:  {"ot", "Ordinary time including extra time"},
		3:  {"fe", "Full event"},
		4:  {"1h", "1st half"},
		5:  {"2h", "2nd Half"},
		6:  {"1q", "1st Quarter"},
		7:  {"2q", "2nd Quarter"},
		8:  {"3q", "3rd Quarter"},
		9:  {"4q", "4th Quarter"},
		10: {"1s", "1st Set"},
		11: {"2s", "2nd Set"},
		12: {"3s", "3rd Set"},
		13: {"4s", "4th Set"},
		14: {"5s", "5th Set"},
		15: {"1r", "1st Round"},
		16: {"2r", "2nd Round"},
		17: {"3r", "3rd Round"},
		18: {"4r", "4th Round"},
		19: {"5r", "5th Round"},
		20: {"6r", "6th Round"},
		21: {"1i", "1st Inning"},
		22: {"2i", "2nd Inning"},
		23: {"3i", "3rd Inning"},
		24: {"4i", "4th Inning"},
		25: {"5i", "5th Inning"},
		26: {"6i", "6th Inning"},
		27: {"7i", "7th Inning"},
		28: {"8i", "8th Inning"},
		29: {"9i", "9th Inning"},
		30: {"f5i", "First 5 innings"},
		31: {"1m", "Map 1"},
		32: {"2m", "Map 2"},
		33: {"3m", "Map 3"},
		34: {"4m", "Map 4"},
		35: {"5m", "Map 5"},
		36: {"6m", "Map 6"},
		37: {"7m", "Map 7"},
		38: {"1p", "1st Period"},
		39: {"2p", "2nd Period"},
		40: {"3p", "3rd Period"},
	}

	if info, ok := marketScopes[scopeFK]; ok {
		return info.Name, info.Description
	}
	return "unknown", "Unknown market scope"
}

// GetMarketDescription generates a human-readable market description
func GetMarketDescription(typeFK, subtypeFK, scopeFK int, dparam float64) string {
	marketType, _ := GetMarketTypeInfo(typeFK)
	marketSubtype, _ := GetMarketSubtypeInfo(subtypeFK)
	marketScope, _ := GetMarketScopeInfo(scopeFK)

	// Format based on market type
	switch typeFK {
	case 1: // 1X2
		selection := ""
		switch subtypeFK {
		case 1:
			selection = "Home Win"
		case 2:
			selection = "Draw"
		case 3:
			selection = "Away Win"
		}
		return fmt.Sprintf("1X2 - %s (%s)", selection, marketScope)

	case 2: // 12 (2Way)
		selection := ""
		switch subtypeFK {
		case 1:
			selection = "Home Win"
		case 3:
			selection = "Away Win"
		}
		return fmt.Sprintf("2Way - %s (%s)", selection, marketScope)

	case 4: // Over/Under
		return fmt.Sprintf("Over/Under %.1f - %s (%s)", dparam, marketSubtype, marketScope)

	case 6: // Asian Handicap
		sign := ""
		if dparam > 0 {
			sign = "+"
		}
		return fmt.Sprintf("Asian Handicap %s%.1f (%s)", sign, dparam, marketScope)

	default:
		return fmt.Sprintf("%s - %s (%s)", marketType, marketSubtype, marketScope)
	}
}
