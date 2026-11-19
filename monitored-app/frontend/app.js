
const API = `${location.protocol}//${location.hostname}:8001`;

let products = [];
let cart = [];
let selectedCategory = "all";

const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;",
        '"': "&quot;", "'": "&#39;"
    })[char]);
}

function money(value) {
    return "₹" + Number(value).toLocaleString("en-IN");
}

function productSymbol(product) {
    const text = `${product.name} ${product.category || ""}`.toLowerCase();

    if (text.includes("keyboard")) return "⌨️";
    if (text.includes("mouse")) return "🖱️";
    if (text.includes("headphone") || text.includes("audio")) return "🎧";
    if (text.includes("phone")) return "📱";
    if (text.includes("laptop")) return "💻";
    if (text.includes("watch")) return "⌚";
    if (text.includes("camera")) return "📷";
    return "✦";
}

function getCategory(product) {
    return product.category || "Accessories";
}

async function loadProducts() {
    const status = $("#status");
    const refresh = $("#refreshProducts");

    status.innerHTML = '<span class="live-dot"></span> Connecting to API...';
    refresh.disabled = true;

    try {
        const response = await fetch(`${API}/products`, {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const data = await response.json();

        if (!Array.isArray(data)) {
            throw new Error("Unexpected product response");
        }

        products = data;
        cart = cart.filter(item =>
            products.some(product => product.id === item.id)
        );

        status.innerHTML =
            `<span class="live-dot"></span> API connected · ${products.length} products`;

        renderFilters();
        renderProducts();
        renderCart();

    } catch (error) {
        status.textContent = `API unavailable: ${error.message}`;
        $("#products").innerHTML = "";
        $("#resultsLabel").textContent = "Unable to load products";
        $("#emptyState").hidden = false;
        $("#emptyState").querySelector("h3").textContent =
            "Store temporarily unavailable";
        $("#emptyState").querySelector("p").textContent =
            "Please try refreshing the product collection.";
    } finally {
        refresh.disabled = false;
    }
}

function renderFilters() {
    const categories = [...new Set(products.map(getCategory))];

    const all = ["all", ...categories];

    $("#filters").innerHTML = all.map(category => `
        <button class="filter ${selectedCategory === category ? "active" : ""}"
            data-category="${escapeHtml(category)}">
            ${category === "all" ? "All products" : escapeHtml(category)}
        </button>
    `).join("");
}

function renderProducts() {
    const query = $("#searchInput").value.trim().toLowerCase();

    const filtered = products.filter(product => {
        const matchesCategory =
            selectedCategory === "all" ||
            getCategory(product) === selectedCategory;

        const matchesSearch =
            String(product.name).toLowerCase().includes(query);

        return matchesCategory && matchesSearch;
    });

    $("#resultsLabel").textContent =
        `${filtered.length} product(s) in this collection`;

    $("#emptyState").hidden = filtered.length !== 0;

    $("#products").innerHTML = filtered.map(product => {
        const inCart = cart.some(item => item.id === product.id);

        return `
            <article class="product">
                <div class="product-visual">
                    <span class="product-badge">CURATED PICK</span>
                    <span class="symbol">${productSymbol(product)}</span>
                </div>
                <div class="product-info">
                    <span class="product-category">
                        ${escapeHtml(getCategory(product))}
                    </span>
                    <h3>${escapeHtml(product.name)}</h3>
                    <div class="product-price">
                        ${money(product.price)}
                    </div>
                    <div class="product-actions">
                        <button class="add-button"
                            data-add="${escapeHtml(product.id)}">
                            ${inCart ? "Add another +" : "Add to bag +"}
                        </button>
                    </div>
                </div>
            </article>
        `;
    }).join("");
}

function addToCart(id) {
    const product = products.find(item => String(item.id) === String(id));
    if (!product) return;

    const existing = cart.find(item => item.id === product.id);

    if (existing) {
        existing.quantity++;
    } else {
        cart.push({ ...product, quantity: 1 });
    }

    renderProducts();
    renderCart();
    showToast(`${product.name} added to your bag`);
}

function changeQuantity(id, change) {
    const item = cart.find(product => String(product.id) === String(id));
    if (!item) return;

    item.quantity += change;

    if (item.quantity <= 0) {
        cart = cart.filter(product => product.id !== item.id);
    }

    renderCart();
    renderProducts();
}

function removeFromCart(id) {
    cart = cart.filter(item => String(item.id) !== String(id));
    renderCart();
    renderProducts();
}

function renderCart() {
    const count = cart.reduce((total, item) => total + item.quantity, 0);
    const total = cart.reduce(
        (sum, item) => sum + Number(item.price) * item.quantity, 0
    );

    $("#cartCount").textContent = count;
    $("#cartTotal").textContent = money(total);

    if (!cart.length) {
        $("#cartItems").innerHTML = `
            <div class="empty-state">
                <span>♡</span>
                <h3>Your bag is empty</h3>
                <p>Explore our collection and add something you love.</p>
            </div>
        `;
        return;
    }

    $("#cartItems").innerHTML = cart.map(item => `
        <div class="cart-item">
            <div>
                <h4>${escapeHtml(item.name)}</h4>
                <p>${money(item.price)} each</p>
                <div class="quantity-controls">
                    <button data-minus="${escapeHtml(item.id)}">−</button>
                    <strong>${item.quantity}</strong>
                    <button data-plus="${escapeHtml(item.id)}">+</button>
                    <button class="remove-item"
                        data-remove="${escapeHtml(item.id)}">Remove</button>
                </div>
            </div>
            <strong>${money(Number(item.price) * item.quantity)}</strong>
        </div>
    `).join("");
}

function openCart() {
    $("#cartDrawer").classList.add("open");
    $("#overlay").classList.add("open");
}

function closeCart() {
    $("#cartDrawer").classList.remove("open");
    $("#overlay").classList.remove("open");
}

let toastTimer;

function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2300);
}

// Event delegation keeps the product grid interactive after rendering.
$("#products").addEventListener("click", event => {
    const button = event.target.closest("[data-add]");
    if (button) addToCart(button.dataset.add);
});

$("#filters").addEventListener("click", event => {
    const button = event.target.closest("[data-category]");
    if (!button) return;

    selectedCategory = button.dataset.category;
    renderFilters();
    renderProducts();
});

$("#searchInput").addEventListener("input", renderProducts);

$("#cartItems").addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;

    if (button.dataset.plus) changeQuantity(button.dataset.plus, 1);
    if (button.dataset.minus) changeQuantity(button.dataset.minus, -1);
    if (button.dataset.remove) removeFromCart(button.dataset.remove);
});

$("#openCart").addEventListener("click", openCart);
$("#closeCart").addEventListener("click", closeCart);
$("#overlay").addEventListener("click", closeCart);
$("#refreshProducts").addEventListener("click", loadProducts);

$("#checkoutButton").addEventListener("click", () => {
    if (!cart.length) {
        showToast("Your shopping bag is empty");
        return;
    }

    showToast("Demo checkout completed — no payment processed");
    cart = [];
    renderCart();
    renderProducts();
    closeCart();
});

loadProducts();
