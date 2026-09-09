// This is where you can change the universe economy
Name = "Economy"

[General]
TurnFrequency                           = 5					// (5) This is how often the economy gets run. 10 = 10 turns
															// Closure of bids is now done within the database server, every turn - so this rate can now be > 1

															// These are the fields to change the ship and auction screen values
[Auction/Ship]
MinimumBidFactor						= 1.0				// The multiplier for the minimum bid for a ship, currently based on BPV
															// note that MinimumBidFactor is similar to TradeIn

TurnsUntilClose							= 3					// Number of turns before a bid on a ship is closed
															// zero means "no wait" (used for single-player)

CanBenefitFromDowngradingShip			= 1					// (1)  1=If player gains a ship that required less prestige than their current ship, they will get the difference as well, 0=Do not award the difference

MaximumAge								= 25				// This is the number of turns before a ship is scrapped
MaximumInReviewByEmpire					= 40				// Currently this is the maximum ships allowed to be available for bid for an empire, regardless of strength/budget.

PlayerModifierStep						= 20				// For every [x] players online when the economy is processed, we increase the budget for production.  It's actually a ratio, so if 10 people are on, production is up 50%.
BuildBaseEconomicThreshold				= 0					// Economy has to be above this threshold before bases are built.
BuildBaseFrequency						= 4					// How often bases try to get built
BuildBigShipEconomicThreshold			= 1					// How healthy an empire has to be to try to build a big ship
BuildBigShipFrequency					= 3					// how often the computer tries to build big ships DN, BB, CV
NormalBuildTriesBeforeGiveUp			= 10				// Number of times the AI will try to be placed in a home hex before being placed randomly


// The cost multiplier for each difficulty setting
[Cost/Difficulty]
0	= 0.5
1	= 1.0
2	= 1.1

// This is the basic chance that a ship will be made by the empire
[Cost/Ship/Build]
Shuttle				= 0.01
Freighter			= 0.03
Frigate				= 0.20
Destroyer			= 0.15
LightCruiser		= 0.15
HeavyCruiser		= 0.10
HeavyBattlecruiser	= 0.10
Dreadnought			= 0.10
Battleship			= 0.10
ListeningPost		= 0.10
Shipyard			= 0.10
BaseStation			= 0.10
BattleStation		= 0.10
StarBase			= 0.10

// This is the cost of supplies in spacedock.
// note that MinimumBidFactor is similar to TradeIn
[Cost/Ship/SupplyDock]
Repair		= 1.0
TradeIn		= 1.0		// This should never be above 1.0 otherwise the player can trade in ship for more than cost of new one!
Missiles	= 1.0
Fighters	= 1.0
Shuttles	= 4.0
Marines		= 4.0
Mines		= 4.0
SpareParts	= 1.0

// This is a modifier per <eClassType> for the price of a ship
// the order must match <enum eClassType>
// all types are included here, but not necessarily used
[Cost/Ship/ClassType]
SHUTTLE					= 1.0
FREIGHTER				= 1.0
FRIGATE					= 0.5
DESTROYER				= 0.55
LIGHT_CRUISER			= 0.6
HEAVY_CRUISER			= 0.7
HEAVY_BATTLECRUISER		= 0.8
DREADNOUGHT				= 1.1
BATTLESHIP				= 1.5
LISTENING_POST			= 1.0
SHIPYARD				= 1.0
BASE_STATION			= 1.0
BATTLE_STATION			= 1.0
STARBASE				= 1.0
MONSTER					= 1.0
PLANET					= 1.0
SPECIAL					= 1.0
