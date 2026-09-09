Name="MissionMatching"

[General]
TurnFrequency						=1

[Monitor]
ViewEngagementServerActivity		= 1		// DEFAULT =1	1=view all engagement server activity, 0=view activity not logged

[Turnbreak]
TurnBreakRatio						=0.3
Mode								=2

[ScreenForMatch]
MatchDetail							= 1		// 0=no detail, 1=minimum detail, 2=max detail in log file/screen
BonusForNearbyForeignCharacters		=100
EnemyHexBonus						=100	// bonus for a mission in enemy territory
NeutralHexBonus						=50		// bonus chance in neutral hexes for a mission
ChanceMove							=30		// (30) base chance for a mission on move (increase for more missions in home territory)
ChanceLogon							=100
ChanceTurnBreak						=10
ChanceMissionComplete				=0
ChanceMissionForfeit				=0
ChanceGoalExpired					=0
ChanceGoalInvalid					=0
ChanceGoalComplete					=0

																	// Add to these if you have special versions of these missions.  They will be equally random, so be careful.  You could always adjust this by having duplicate entries
																	// of those that should be more common.  (For example, if you had an extra Meta_Hail called Meta_Hail_StarIsGoingNova and wanted it 10% of the time, have it once and Meta_Hail
																	// appear 9 times...)
[HailMissions/HailMissionTitles]
0									="Meta_Hail"					// Title of Hail mission (special)

[HailMissions/HailConvoyMissionTitles]
0									="Meta_Hail_Convoy"				// Used when player attacks a AI Convoy

[HailMissions/HailBaseStationMissionTitles]
0									="Meta_Hail_Base"				// Used when player attacks a Base Station AI

[HailMissions/HailBattleStationMissionTitles]
0									="Meta_Hail_Base"				// Used when player attacks a Battle Station AI

[HailMissions/HailStarBaseMissionTitles]
0									="Meta_Hail_Base"				// Used when player attacks a Starbase AI

[HailMissions/HailPlanetMissionTitles]
0									="Meta_Hail_Planet"				// Used when player attacks a Planet AI

[HailMissions/HailHomePlanetMissionTitles]
0									="Meta_Hail_Homeworld"			// Used when player attacks a Home Planet AI

[HailMissions/HailShipYardMissionTitles]
0									="Meta_Hail_ShipYard"			// Used when player attacks a Ship Yard AI

[MissionProfiles]
ShowMission							=0		// (0) shows the team's mission title, 1 show's the true mission title
HasMustPlayMissions					=1		// (1) Server will dispense must play missions 
MustPlayOnlyOnEnemyHex				=0		// (0) Server ignores mission script settings and will only set must plays when player is in an enemy hex (HasMustPlayMissions must be set!)
Move								=2
Logon								=1
TurnBreak							=0
MissionComplete						=1
MissionForfeit						=0
GoalExpired							=0
GoalInvalid							=0
GoalComplete						=0
RandMssnInBaseOrPlanetHex				=1	// Do you allow random (single player missions, like scan and distress call, in hexes with bases and planets? 1 for yes 0 for no)
AllowRandomMissionsIfEnemyInHex				=1	// If there is someone to attack, should a random mission like scan be available for the player?

[MissionScoring]
ByMainCharacter						=1.0
ByOtherCharacters					=1.0
MonteCarloMissionSelect				=0		// (0) Currently unsupported
MaxMonteCarloTries					=10
MaxSequenceScore					=1000

//weight to missions matching based on terrain
[TerrainScoring]
PlanetTypeScoreForMatching			=750  
BaseTypeScoreForMatching			=250
TerrainTypeScoreForMatching			=100

//weight to missions matching based on political tensions
[PoliticsScoring]
BonusForExactPoliticalMatch			=1000
LookingForOwnHexInOwn				=1000
LookingForOwnHexInAlly				=500
LookingForOwnHexInNeutral			=0
LookingForOwnHexInEnemy				=-100
LookingForEnemyHexInOwn				=-100
LookingForEnemyHexInAlly			=-100
LookingForEnemyHexInNeutral			=0
LookingForEnemyHexInEnemy			=1000
LookingForAllyHexInOwn				=0
LookingForAllyHexInAlly				=1000
LookingForAllyHexInNeutral			=0
LookingForAllyHexInEnemy			=-100

//weight to missions matching based on ships available
[FleetScoring]
GoodBPVScore						=1000
TooWeakBPVScore						=300
TooStrongBPV						=0
GoodShipCountScore					=0
TooFewShipCountScore				=0
TooManyShipCountScore				=0
PlaceBaseMissionScore				=50000
BaseScoreBonus						=10000

// weights of categories
[ScoringWeights]
WeightMissionsLastPlayed			=0.2
WeightPoliticsScore					=10.0
WeightTerrainScore					=1.0
WeightFleetScore					=0.01

[RelationshipScoring]
MaxRelationShipScore				=1000
PoorEnemyOfScore					=100
PoorAllyOfScore						=200
DecentWorstEnemyScore				=300
DecentAllyOfScore					=200
OrionDomesticWeight					=0.7
OrionNeutralWeight					=.3
OrionEnemyWeight					=0.2			 

[RecentlyPlayedScoring]
MaxLastPlayedScore					=1000
NumMissionsTracked					=5

[MapScoring]
PlanetScore							=20
TerrainScore						=10
BaseScore							=30

[AssignCharactersToSlots]
AllowHumanToHumanMatching			= 1
MonteCarloSelectPlayer				= 0
MinimumScoreToAssignToSlot			= 300

[Game]
GameSpeed							=7 	//default meta game speed
SessionName							="DynaverseIII" //server name

// Time to wait for missions selection in milliseconds
[SetupProtocol]
ResponseWait						=120000
ReadyWait							=60000

//modifier based difficulty setting
[Diff]
CaptainDiff							=0.85
CommodoreDiff						=1.0
AdmiralDiff							=1.15

// Space backgrounds used
[Backgrounds]
0									="space00.mod"
1									="space01.mod"
2									="space02.mod"
3									="space03.mod"
4									="space04.mod"
5									="space05.mod"
6									="space06.mod"
7									="space07.mod"
8									="space08.mod"
9									="space09.mod"
10									="space10.mod"
11									="space11.mod"
12									="space12.mod"
13									="space13.mod"
14									="space14.mod"
15									="space15.mod"
16									="space16.mod"
17									="space17.mod"
18									="space18.mod"
19									="space19.mod"
20									="space20.mod"
21									="space21.mod"
22									="space22.mod"
23									="space23.mod"
24									="space24.mod"
25									="space25.mod"
26									="space26.mod"
27									="space27.mod"
28									="space28.mod"
29									="space29.mod"
30									="space30.mod"
31									="space31.mod"

[ForfeitModifiers]
ForfeitPercentageLossOfPrestige					= 25		// (25)		On a forfeit, the player will lose this percentage of their total prestige.
ForfeitPrestigeThreshold						= 10		// (5000)	At or below this prestige level, the player will instead lose their ship on a forfeit.
ForfeitLoseShipIfBelowPrestigeThreshold			= 0			// (0)		1= Lose ship if forfeit and below prestige threshold, 0= Player will not lose ship - just more prestige (ignore threshold)
ForfeitIfFailedToJoin							= 0			// (0)		1= Treat "failure to join battle with other humans" or "disconnect before reporting battle results" as a forfeit, 0=Ignore this option
DisreputeIfFailedToJoin							= 1			// (0)		1= Treat "failure to join battle with other humans" or "disconnect before reporting battle results" as a loss of disrepute, 0=Ignore this option
DisreputeLostOnFailedToJoin						= 1000		// (1000)	Amount of disrepute to charge the player if they fail to join or disconnect early.
MoveToFriendlyBaseIfFailedToJoin				= 1			// (1)		(NOTE: ignored, unless DisreputeIfFailedToJoin=1)	1=Move player to nearest friendly starbase/planet as well, 0=leave them in the hex
LoseStarbaseIfFailedToJoin						= 0			// (0)		(NOTE: ignored, unless DisreputeIfFailedToJoin=1)	1=Player loses their starbase seed as well, 0=Nothing happens to their starbase seed
DeathIfFailedToJoin								= 0			// (0)		1= Treat "failure to join battle with other humans" or "disconnect before reporting battle results" as a death in battle, 0=Ignore this option
															// WARNING: The "IfFailedToJoin" options are for CHEATERS.  Be careful that you don't use all at once, as they are cumulative - NOT exclusive.

[EngagementTimers]
EngagementServerTickRate			= 1000		// time in ms
WaitForBattleStart					= 20000		// time in ms before battle starts and no one else will join (battle is resolved to play/or not at that point)
WaitForMissionReception				= 25000		// time in ms allowing players to acknowledge receipt of mission, ready to start
WaitForBattleResults				= 480		// time in minutes before Engagement server assumes all players failed to report battle and are forfeited.
WaitForRemainingBattleResults		= 480000	// time in ms for remaining battle results to be reported after first was reported

[EngagementMisc]
MaxPlayersInEngagement				= 6			// Max # of players that can engage each other at one time (will change to 8)
DefenderFledAttackerBonus			= 125		// Prestige bonus to attackers if battle did not start because primary defender forfeited

[PureAIBattle]
OddsAstoundingVictory				= 5			// 0..100 Odds that one side of pure AI battle will get Astounding Victory
OddsVictory							= 20		// 0..100 Odds that one side of pure AI battle will get Victory
OddsDefeat							= 20		// 0..100 Odds that one side of pure AI battle will get Defeat
OddsDevastatingDefeat				= 5			// 0..100 Odds that one side of pure AI battle will get Devastating Defeat
DefenderHomeHexAdvantage			= 2			// Bonus to odds for defender if battle is within friendly hex
AttackerHomeHexAdvantage			= 0			// Bonus to odds for attacker if battle is within friendly hex

												// Battle formula (calculated for defender):
												// ratio = defender's total BPV / attacker's total BPV
												// 
												// if ( defender is battling on home territory )
												// {
												//      OddsVictory += DefenderHomeHexAdvantage
												// }
												// 
												// if ( attacker is battling on home territory )
												// {
												//      OddsDefeat += AttackerHomeHexAdvantage
												// }
												// 
												// OddsAstoundingVictory *= ratio
												// OddsVictory           *= ratio
												// OddsDefeat            *= 1/ratio
												// OddsDevastatingDefeat *= 1/ratio
												// 
												// OddsDraw				 = ( 100 - OddsAstoundingVictory - OddsVictory - OddsDefeat - OddsDevastatingDefeat )
												// if ( OddsDraw < 0 )
												// {
												//      OddsDraw = 0
												//      Remaining odds are normalized
												// }
OddsDeathOnDevastatingDefeat		= 95		// 0..100 Odds that AI will die as a result of devastating defeat
OddsDeathOnDefeat					= 65		// 0..100 Odds that AI will die as a result of defeat

DamageRange							= 80		// 0..100 Percentage damage on single system in one random damage pass
OddsShipSystemDamage				= 50		// 0..100 Odds that random ship damage is system damage
DamagePassesOnDevastatingDefeat		= 20		// Number of passes of random damage on ship as a result of devastating defeat (assuming they weren't killed)
DamagePassesOnDefeat				= 10		// Number of passes of random damage on ship as a result of defeat
DamagePassesOnDraw					= 5			// Number of passes of random damage on ship as a result of a draw
DamagePassesOnVictory				= 2			// Number of passes of random damage on ship as a result of victory
DamagePassesOnAstoundingVictory		= 0			// Number of passes of random damage on ship as a result of astounding victory

PrestigeForAstoundingVictory		= 350		// Prestige for AI astounding victory
PrestigeForVictory					= 250		// Prestige for AI victory
PrestigeForDraw						= 0			// Prestige for AI draw
PrestigeForDefeat					= -250		// Prestige for AI defeat
PrestigeForDevastatingDefeat		= -350		// Prestige for AI devastating defeat

AIBattlesSimulateTime				= 1			// (1)  1=Simulate time delay before resolution of pure AI battle, 0=resolve results immediately
AIBattlesTimeRange					= 5			// (5)	Time in minutes/seconds that pure AI battle might take (random)
AIBattlesTimeInMinutes				= 1			// (1)	1=AIBattlesTimeRange is in minutes, 0=AIBattlesTimeRange is in seconds

[Fleet]
LeaderCannotBeLowerClassThanMember	= 1			// (1)	1=This prevents a member from joining a fleet if they have a higher ship class than the leader.  IGNORES freighters as leaders., 0=no check

[Fleet/Maximum]
Freighter							= 1			// (1)  Maximum of this ship class in a fleet (freighters cannot join anyway, so they're always 1)
Frigate								= 3			// (3)
Destroyer							= 3			// (3)
LightCruiser						= 3			// (3)
HeavyCruiser						= 2			// (2)
HeavyBattlecruiser					= 1			// (1)
Dreadnought							= 1			// (1)
Battleship							= 1			// (1)
