Name="AI"

[General]
TurnFrequency						= 4			// This is how often the AI server gets updated 1=1 time a turn

// This section handles the creation of AI ships
[Census]
TargetPopulationToEconomicRatio		= 0.09		// 0.0025 // (0.0025) This is the ratio of AI ships to current economy of an empire

StandardAIBPV						= 5000		// Default AI BPV (currently ignored)
MaxAIEcoBonusBPV					= 2.0		// Higher number will make bigger AI ships for losing empires
MinFuzzAIBPV						= 0.3		// Minimum random AI bpv level 0.3 = 30% less
MaxFuzzAIBPV						= 3.0		// Maximum random AI bpv level 2.0 = twice base

MaxAIsToCreatePerTurn				= 50		// How many AIs to try to create before giving up
CreateAIFrequency					= 1			// How many AIs to create a second, until goal level reached
KillAIFrequency						= 2			// How many AIs to kill a second, until goal level reached (this only applies to mission generated AIs)
CreateOfficerFrequency				= 1			// How many officers to create a second, until goal level reached
MaxAIsPerEmpire						= -1		// ( -1 ) Create a fixed number of AIs per empire. -1 means not to use a fixed number.

[Rating]
StartingAIRating					= 1200
StartingAIRatingRange				= 500

												// Difficulty levels are 0, 1, 2
[CreateShipClassOdds/0]
Freighter							= 25		// (25)		Odds (out of total) to start a given AI in this ship
Frigate								= 20		// (20)
Destroyer							= 15		// (15)
LightCruiser						= 10		// (10)
HeavyCruiser						= 5			// (5)
HeavyBattlecruiser					= 2			// (2)
Dreadnought							= 2			// (2)
Battleship							= 1			// (1)

[CreateShipClassOdds/1]
Freighter							= 25		// (25)
Frigate								= 15		// (15)
Destroyer							= 30		// (30)
LightCruiser						= 25		// (25)
HeavyCruiser						= 20		// (20)
HeavyBattlecruiser					= 15		// (15)
Dreadnought							= 10		// (10)
Battleship							= 1			// (5)

[CreateShipClassOdds/2]
Freighter							= 25		// (25)
Frigate								= 15		// (15)
Destroyer							= 30		// (30)
LightCruiser						= 30		// (30)
HeavyCruiser						= 20		// (20)
HeavyBattlecruiser					= 15		// (15)
Dreadnought							= 10		// (10)
Battleship							= 1			// (1)


// Officers
[Officers]
MaxInReviewByClient					= 8			// (8)		This is the most a human player can view in the officer screen (marked as in review and made available to client for a period of time)
MaxInReviewTime						= 10		// (10)		# of minutes the client has to review officers before D3 asks for them back
OfficerPopulationRatio				= 30.0		// (30.0)	Multiplied by the # of characters of a race to determine # of officers for that race

[Officers/MinAtBase]
ListeningPost						= 2			// (2)		Regardless of population, bases of this type will have at least this # of officers
Shipyard							= 4			// (4)
BaseStation							= 10		// (10)
BattleStation						= 12		// (12)
StarBase							= 16		// (16)
Planet								= 20		// (20)

[Officers/AvgAtBase]
ListeningPost						= 4			// (4)		When filling the bases, will fill to this amount for all bases first, then will repeat with any leftovers until max (below)
Shipyard							= 8			// (16)
BaseStation							= 18		// (32)
BattleStation						= 64		// (64)
StarBase							= 96		// (96)
Planet								= 128		// (128)

[Officers/MaxAtBase]
ListeningPost						= 6			// (6)		Maximum officers available at this type of base
Shipyard							= 64		// (64)
BaseStation							= 128		// (128)
BattleStation						= 512		// (512)
StarBase							= 2048		// (2048)
Planet								= 4096		// (4096)
