Name = "MissionGoals"

//[Fed_HappyFleet]

[Fed_Rendezvous]
GoalDescription="You have 6 turns to refit at the nearest starbase.  Then Starfleet requires you to rendezvous at hex 8,10."

[Fed_Rendezvous/Goals]
0="Time Wait 6"
1="Location Move Hex 8 10 Wander 0"
2="Package Deliver Fed_Rendezvous"

[Fed_Rendezvous/HexChanges]
0="Hex 12 14 Race Klingon"
1="Hex 14  8 Race Romulan"
2="Hex 13  8 Race Romulan"
3="Hex 12  9 Race Romulan"

[Fed_Reception]
GoalDescription="Starfleet now needs you at hex 11,10."

[Fed_Reception/Goals]
0="Location Move Hex 11 10 Wander 0"
1="Package Deliver Fed_Reception"

[Fed_GrayArea]
GoalDescription="Starfleet requires your presence at hex 9,8."

[Fed_GrayArea/Goals]
0="Location Move Hex 9 8 Wander 0"
1="Package Deliver Fed_GrayArea"

// [Fed_Stakeout]
// [Fed_ProcessOfElimination]
// [Fed_ConspiracyOfTheConcerned]
// [Fed_TerranIncognito]
// [Fed_Counter]
// [Fed_ForcedEntry]
// [Fed_RoundUp]
// [Fed_Elusive]
// [Fed_Scorched]
// [Fed_Luddite]
// [Fed_NoReturn]

// [Kli_Brotherhood]
// [Kli_TooFar]
// [Kli_AVastYeScurvyTargs]

[Kli_WindsOChange]
GoalDescription="Klingon High Command commands you to rendezvous at hex 4,9 immediately."

[Kli_WindsOChange/Goals]
0="Location Move Hex 4 9 Wander 0"
1="Package Deliver Kli_WindsOChange"

[Kli_AnviloPeace]
GoalDescription="Klingon High Command commands you to move to hex 6,7 without delay."

[Kli_AnviloPeace/Goals]
0="Location Move Hex 6 7 Wander 0"
1="Package Deliver Kli_AnviloPeace"

// [Kli_TurningTables]
// [Kli_FishBarrel]
// [Kli_Obedience]
// [Kli_EDuty]
// [Kli_Barking]
// [Kli_FDay]
// [Kli_FriendOrFoe]
// [Kli_Recall]
// [Kli_Blood]

[Rom_EveryRock]
GoalDescription="Romulan Star Empire requires you to rendezvous at hex 11,9 immediately."

[Rom_EveryRock/Goals]
0="Location Move Hex 11 9 Wander 0"
1="Package Deliver Rom_EveryRock"

[Rom_SoundoVictory]
GoalDescription="Romulan Star Empire requires your presence at hex 11,9 without further delay."

[Rom_SoundoVictory/Goals]
0="Location Move Hex 11 9 Wander 0"
1="Package Deliver Rom_SoundoVictory"

// [Rom_ProfitMotive]
// [Rom_Ishmael]
// [Rom_Giants]
// [Rom_UltimateDuty]
// [Rom_Quietly]
// [Rom_Sneakers]
// [Rom_KM]
// [Rom_GrayArea]
// [Rom_Cats]
// [Rom_Barrows]
// [Rom_Shiny]
// [Rom_MakeMe]

[Rom_Sheep]
GoalDescription="Romulan Star Empire requires that you head to hex 8,13 immediately."

[Rom_Sheep/Goals]
0="Location Move Hex 8 13 Wander 0"
1="Package Deliver Rom_Sheep"

// [Rom_Trojan]
// [Rom_Salt]
