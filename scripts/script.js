const text = "Olá! :)";
const h1 = document.getElementById("typing-text");

let index = 0;

function type() {
  h1.textContent += text[index];
  index++;

  if (index < text.length) {
    setTimeout(type, 100); 
  }
}

type();

function showPopup() {
  var popup = document.getElementById("popup");
  popup.style.display = "block";
  setTimeout(function () {
      popup.style.display = "none";
  }, 5000);
};
