Name="MetaMap"

[General]
TurnFrequency						= 3			// (3) This is how often the map gets updated 1=1 time a turn
CauseTurnBreakOnMove 				= 0			// (0) This is set to 1 to cause the player to create a turn break by moving.  (This setting must be 0 on server side!)
 
[Movement]
Radius=1										// This is the number of hexes the AI looks at to determine where to move.
MovementDelayInMilliseconds			= 15000		// This is how long it take to move 1 space on the map in milliseconds (multiplied by impedence of hex)
CarryingStarbaseDelay				= 45000		// This is how long it take to move 1 space on the map in milliseconds if you are carrying a starbase! (multiplied by impedence of hex)

[StarbasePlacement]
UnlimitedBasesInHex					= 0			// 0=can only have one base in a hex, 1=unlimited # of bases in hex.
MinNearbySameRaceHexes				= 2			// There are 6 possible surrounding hexes.  At least this many must be of the same race as the current hex (which must match player's race)

[PoliticalTensionInc]
												// This is the numbered added every time a battle is fought
												// Some races like the Federation are slower to anger
Federation=0			// 5
Klingon=0				// 20
Romulan=0				// 10
Borg=0					// 15
Species8472=0			// 10
Cardassian=0			// 10
Ferengi=0				// 15
Rakellian=0				// ?
Pirate=0				// ?
Neutral=0				// 25


[PoliticalTensionDec]
												// This is the number subtracted when political tension is asked to be decreased.
												// The federation is more likely to forgive than other races
Federation=0			// 75
Klingon=0				// 15
Romulan=0				// 30
Borg=0					// 30
Species8472=0			// 10
Cardassian=0			// 45
Ferengi=0				// 30
Rakellian=0				// ?
Pirate=0				// ?
Neutral=0				// 10


[PoliticalTension/StartingTensions/Federation]
Federation=0
Klingon=800
Romulan=800
Borg=1000
Species8472=1000
Cardassian=800
Ferengi=200
Rakellian=1000
Pirate=1000
Neutral=800

[PoliticalTension/StartingTensions/Klingon]
Federation=800
Klingon=0
Romulan=800
Borg=1000
Species8472=1000
Cardassian=800
Ferengi=200
Rakellian=1000
Pirate=1000
Neutral=800

[PoliticalTension/StartingTensions/Romulan]
Federation=800
Klingon=800
Romulan=0
Borg=1000
Species8472=1000
Cardassian=1000
Ferengi=200
Rakellian=1000
Pirate=1000
Neutral=800


[PoliticalTension/StartingTensions/Borg]
Federation=1000
Klingon=1000
Romulan=1000
Borg=0
Species8472=1000
Cardassian=1000
Ferengi=1000
Rakellian=0
Pirate=0
Neutral=1000

[PoliticalTension/StartingTensions/Species8472]
Federation=1000
Klingon=1000
Romulan=1000
Borg=1000
Species8472=0
Cardassian=1000
Ferengi=1000
Rakellian=1000
Pirate=1000
Neutral=1000


[PoliticalTension/StartingTensions/Cardassian]
Federation=800
Klingon=800
Romulan=1000
Borg=1000
Species8472=1000
Cardassian=0
Ferengi=200
Rakellian=1000
Pirate=1000
Neutral=800


[PoliticalTension/StartingTensions/Ferengi]
Federation=200
Klingon=200
Romulan=200
Borg=1000
Species8472=1000
Cardassian=200
Ferengi=0
Rakellian=1000
Pirate=1000
Neutral=800


[PoliticalTension/StartingTensions/Rakellian]
Federation=200
Klingon=200
Romulan=200
Borg=1000
Species8472=1000
Cardassian=200
Ferengi=200
Rakellian=0
Pirate=1000
Neutral=800

[PoliticalTension/StartingTensions/Pirate]
Federation=200
Klingon=200
Romulan=200
Borg=1000
Species8472=1000
Cardassian=200
Ferengi=200
Rakellian=1000
Pirate=0
Neutral=800


[PoliticalTension/StartingTensions/Neutral]
Federation=800
Klingon=800
Romulan=800
Borg=1000
Species8472=1000
Cardassian=800
Ferengi=800
Rakellian=1000
Pirate=1000
Neutral=0


[Politics]
NumCycleUpTensions					= 10		// This will add up the increase in tension level every x number of turns
AllyRatio							= 0.25 		// This number determines what percentage of races are allies. Calculated vs most hated enemy
NeutralRatio						= 0.5 		// This number determines what percentage of races are nuetral. Calculated vs most hated enemy
DistanceWeight						= 1.0
TensionWeight						= 1.5
LowNewsRangeUpTo					= 0.25
HighNewsRangeNotBelow				= 0.5

[Battle]
MinVictoryPointsForPlayerVictory	= 0.1
MinVictoryPointsForAIVictory		= 0.1
HexHealthResetRatio					= 0.1

[VictoryPointModifier]
Easy								= 35
Med									= 15
Hard								= 5
PureAI								= 0.05

[TensionBumps]
Draw								= 0.5
SuccessWin							= 0.33
FailedWin							= 0.66
SuccessDefend						= 0.5
FailDefend							= 1.0

[EconomicReport]
Interval							= 10		// Every "Interval" years the report is produced in the news

[WinConditions]
NumCumulativeOpponentsToWin			= 3			// Number of cumulative oppenent points to overcome to win
NumCumulativeOpponentsToWarn		= 2			// Number of cumulative oppenent points to overcome to warn
CumulativeCoefficient				= 1.0		// Coefficient to cumulative points for opponents

[Walk]
WalkRate							= 2000		// (ms)  Delay between each move when walking a character somewhere (goal for human)

[AIBirthPlace]
AIBornOnlyOnBases					= 0			// (0) 0=born either on base, or within a hex of base (random)
AIBornOnBaseOddsDelta				= 4			// (4) Will randomly choose from a list that includes the hexes around a random base and this many occurences of the base hex itself.
												// In other words, 4 would be a 40% chance that the AI would be born on the base itself.  6 would be 50%, 12 would be 66%, and so on...
