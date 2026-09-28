// Card database. Add a new entry here for every card in the game.
//   id        – short unique code, this is what the QR code on the card contains
//   image     – optional artwork shown in the hologram (put files in images/)
//   verses    – each verse becomes its own hologram slide
// Verse text is the King James Version (public domain). Swap in any
// translation you like (e.g. Indonesian) by editing the text fields.
window.CARDS = [
  {
    id: "eve",
    no: "001",
    testament: "Old Testament",
    name: "Eve",
    title: "The Mother of All Living",
    image: "images/eve.jpg",
    ability: "Choose another player to draw 1. If Adam has been played, that player draws 2 instead.",
    sin: 1,
    reference: "Genesis 3:20",
    verses: [
      { n: 20, text: "And Adam called his wife's name Eve; because she was the mother of all living." }
    ]
  },
  {
    id: "serpent",
    no: "001",
    testament: "Old Testament",
    name: "Serpent",
    title: "The Deceiver",
    image: "images/serpent.jpg",
    ability: "Choose a player. Their next Action has no effect and fill the Sin Meter to full.",
    sin: 0,
    reference: "Genesis 3:1–5",
    verses: [
      { n: 1, text: "Now the serpent was more subtil than any beast of the field which the LORD God had made. And he said unto the woman, Yea, hath God said, Ye shall not eat of every tree of the garden?" },
      { n: 2, text: "And the woman said unto the serpent, We may eat of the fruit of the trees of the garden:" },
      { n: 3, text: "But of the fruit of the tree which is in the midst of the garden, God hath said, Ye shall not eat of it, neither shall ye touch it, lest ye die." },
      { n: 4, text: "And the serpent said unto the woman, Ye shall not surely die:" },
      { n: 5, text: "For God doth know that in the day ye eat thereof, then your eyes shall be opened, and ye shall be as gods, knowing good and evil." }
    ]
  },
  {
    id: "adam",
    no: "001",
    testament: "Old Testament",
    name: "Adam",
    title: "The First Man",
    image: "images/adam.jpg",
    ability: "Choose another player to draw a card. If this is the first Character you play in this game, all players except you draw 1 card.",
    sin: 1,
    reference: "Genesis 2:7",
    verses: [
      { n: 7, text: "And the LORD God formed man of the dust of the ground, and breathed into his nostrils the breath of life; and man became a living soul." }
    ]
  }
];
