Name="Score"

[General]
TurnFrequency				= 1

[Rating]
FermiTemp					= 1.0
StartingHumanRating			= 1500
MaximumGain					= 32

[VictoryLevels]
AstoundingVictory			= 1.0
Victory						= 0.8
Draw						= 0.5
Defeat						= 0.2
DevastatingDefeat			= 0.0

[Hex]
WinThreshold				= 0.5

[Misc]
MissionCompletePrestige		= 5				// This is the min level of prestige a player can get if they drop into a tactical game
CombatDamageBonus			= 15			// This is the bonus players get if they come into space dock with zero prestige
ChargeForReplacementShip	= 1				// (1)		1=If the player loses their ship due to forfeit or battle death they will be charged the cost of their new ship, 0=Do not charge player when replacing ship
ChargeToDisreputeRate		= 80			// (80)		Percentage charged to character's disrepute for replacement ship (remainder goes to prestige).  If they already have disrepute, charge up to the amount (difference) and the rest to prestige.

[Base]
PostBattleMinimumRepair		= 1
PostBattleRepairRatio		= 0.25			// Maximum percentage of remaining damage to repair on a base after a battle - PostBattleMinimumRepair
PostBattleMinimumResupply	= 1
PostBattleResupplyRatio		= 0.60			// Maximum percentage of missing stores to resupply a base after a battle - PostBattleMinimumResupply

[Base/Transition]
MinimumVictoryPoints		= 1				// The minimum number of victory points a hex will have after a base transition

[StarBase/Transition/VictoryPoints]
Primary						= 20			// 20 points added if the a StarBase is added or 20 points removed if StarBase is removed.  For the hex the StarBase is placed on
Secondary					= 7				// 7 "" "" but for "secondary" hexes.  Like the one right next to the primary hex

[BattleStation/Transition/VictoryPoints]
Primary						= 14
Secondary					= 4

[BaseStation/Transition/VictoryPoints]
Primary						= 10
Secondary					= 2

[ListeningPost/Transition/VictoryPoints]
Primary						= 2
Secondary					= 0

[WeaponsPlatform/Transition/VictoryPoints]
Primary						= 5
Secondary					= 0

[ShipYard/Transition/VictoryPoints]
Primary						= 4
Secondary					= 0

[LevelUp]										// The odds that an officer will level-up in a skill out of his area of expertise after a mission is completed.
Basic			= 0.0
Trained			= 0.0
Skilled			= 0.0
Veteran			= 0.0
Expert			= 0.0

[SpecializedLevelUp]							// The odds that an officer will level-up in a skill in his area after a mission is completed.
Basic			= 0.100
Trained			= 0.060
Skilled			= 0.040
Veteran			= 0.020
Expert			= 0.010
