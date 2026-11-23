// launch_checkout.js —— Inyecta Google One, consulta el SKU especificado y abre el checkout de Play
//
// Uso: cargado por launch_checkout.py; cambia TARGET_PRODUCT abajo o usa --sku.
// Los resultados se envían con send(): setup / products / offer / launched / purchase_cb, etc.
// 【No pulsa "Suscribirse" automáticamente】: la confirmación en pantalla es manual.
var TARGET_PRODUCT = "g1.20tb";   // ← Cambia aquí el SKU objetivo
var MODULE_APK = "/data/local/tmp/module_521.apk";

Java.perform(function () {
    var context = Java.use("android.app.ActivityThread").currentApplication().getApplicationContext();
    var Activity = Java.use("android.app.Activity");
    var ArrayList = Java.use("java.util.ArrayList");
    var List = Java.use("java.util.List");
    var Handler = Java.use("android.os.Handler");
    var Looper = Java.use("android.os.Looper");

    // --- Carga BillingClient desde el APK modular (Google One no expone esta librería directamente) ---
    var DexClassLoader = Java.use("dalvik.system.DexClassLoader");
    var dexLoader = DexClassLoader.$new(
        MODULE_APK,
        context.getCodeCacheDir().getAbsolutePath(),
        null,
        context.getClassLoader()
    );
    Java.classFactory.loader = dexLoader;

    var BillingClient = Java.use("com.android.billingclient.api.BillingClient");
    var QueryProductDetailsParams = Java.use("com.android.billingclient.api.QueryProductDetailsParams");
    var QpdProduct = Java.use("com.android.billingclient.api.QueryProductDetailsParams$Product");
    var BillingFlowParams = Java.use("com.android.billingclient.api.BillingFlowParams");
    var BfpProductDetailsParams = Java.use("com.android.billingclient.api.BillingFlowParams$ProductDetailsParams");
    var PurchasesUpdatedListener = Java.use("com.android.billingclient.api.PurchasesUpdatedListener");
    var BillingClientStateListener = Java.use("com.android.billingclient.api.BillingClientStateListener");
    var ProductDetailsResponseListener = Java.use("com.android.billingclient.api.ProductDetailsResponseListener");
    var ProductDetails = Java.use("com.android.billingclient.api.ProductDetails");
    var SubscriptionOfferDetails = Java.use("com.android.billingclient.api.ProductDetails$SubscriptionOfferDetails");
    var PricingPhase = Java.use("com.android.billingclient.api.ProductDetails$PricingPhase");

    function S(o) { try { send(o); } catch (e) {} }

    // --- Callback de resultado de compra (al confirmar o cancelar en el checkout) ---
    var purchaseListener = Java.registerClass({
        name: "com.frida.paid.PL",
        implements: [PurchasesUpdatedListener],
        methods: {
            onPurchasesUpdated: function (br, purchases) {
                S({ ev: "purchase_cb", code: br.getResponseCode(), msg: String(br.getDebugMessage() || "") });
            }
        }
    }).$new();

    // enablePendingPurchases es obligatorio; de lo contrario build() lanza excepción
    var bc = BillingClient.newBuilder(context).setListener(purchaseListener).enablePendingPurchases().build();

    // --- Conexión al servicio de facturación: al conectar, ejecuta la consulta en el hilo principal ---
    var stateListener = Java.registerClass({
        name: "com.frida.paid.SL",
        implements: [BillingClientStateListener],
        methods: {
            onBillingSetupFinished: function (result) {
                S({ ev: "setup", code: result.getResponseCode() });
                if (result.getResponseCode() !== 0) return;
                Java.classFactory.loader = null;
                var mainHandler = Handler.$new(Looper.getMainLooper());
                Java.classFactory.loader = dexLoader;
                var Runnable = Java.use("java.lang.Runnable");
                mainHandler.post(Java.registerClass({
                    name: "com.frida.paid.QR",
                    implements: [Runnable],
                    methods: { run: function () { doQuery(); } }
                }).$new());
            },
            onBillingServiceDisconnected: function () { S({ ev: "disc" }); }
        }
    }).$new();

    function doQuery() {
        var prodList = ArrayList.$new();
        prodList.add(QpdProduct.newBuilder().setProductId(TARGET_PRODUCT).setProductType("subs").build());
        var params = QueryProductDetailsParams.newBuilder().setProductList(prodList).build();
        bc.queryProductDetailsAsync(params, Java.registerClass({
            name: "com.frida.paid.PDL",
            implements: [ProductDetailsResponseListener],
            methods: { onProductDetailsResponse: function (br, pdList) { onProducts(br, pdList); } }
        }).$new());
    }

    // --- Obtiene el Activity en primer plano por reflexión sobre ActivityThread.mActivities ---
    function getActivity() {
        try {
            Java.classFactory.loader = null;
            var AT = Java.use("android.app.ActivityThread");
            var acts = AT.currentActivityThread().mActivities.value;
            var it = acts.values().iterator();
            while (it.hasNext()) {
                var rec = it.next();
                var f = rec.getClass().getDeclaredField("activity");
                f.setAccessible(true);
                var a = Java.cast(f.get(rec), Activity);
                if (!a.isFinishing() && !a.isDestroyed()) { Java.classFactory.loader = dexLoader; return a; }
            }
            Java.classFactory.loader = dexLoader;
        } catch (e) {
            Java.classFactory.loader = dexLoader;
            S({ ev: "act_err", m: String(e) });
        }
        return null;
    }

    function onProducts(br, pdList) {
        var list = Java.cast(pdList, List);
        S({ ev: "products", n: list.size() });

        // Toma la primera oferta del SKU objetivo (plan base de pago)
        var targetPd = null, targetOffer = null;
        for (var i = 0; i < list.size(); i++) {
            var pd = Java.cast(list.get(i), ProductDetails);
            var pid = String(pd.getProductId());
            var offers = pd.getSubscriptionOfferDetails();
            if (offers == null) continue;
            var ol = Java.cast(offers, List);
            for (var j = 0; j < ol.size(); j++) {
                var o = Java.cast(ol.get(j), SubscriptionOfferDetails);
                var first = Java.cast(Java.cast(o.getPricingPhases().getPricingPhaseList(), List).get(0), PricingPhase);
                S({ ev: "offer", product: pid, id: String(o.getOfferId()),
                    micros: String(first.getPriceAmountMicros()),
                    period: String(first.getBillingPeriod()) });
                if (pid === TARGET_PRODUCT && targetPd == null) { targetPd = pd; targetOffer = o; }
            }
        }
        if (!targetPd || !targetOffer) { S({ ev: "no_offer" }); return; }

        var token = targetOffer.getOfferToken();
        var finalPd = targetPd, finalToken = token;

        // Espera 1.5s antes de abrir el checkout en el hilo UI para estabilizar el Activity
        Java.classFactory.loader = null;
        var launchHandler = Handler.$new(Looper.getMainLooper());
        Java.classFactory.loader = dexLoader;
        launchHandler.postDelayed(Java.registerClass({
            name: "com.frida.paid.LR",
            implements: [Java.use("java.lang.Runnable")],
            methods: {
                run: function () {
                    try {
                        var uiAct = getActivity();          // Reobtiene el Activity actual en el hilo UI
                        if (!uiAct) { S({ ev: "no_activity_ui" }); return; }
                        var pdp = BfpProductDetailsParams.newBuilder()
                            .setProductDetails(finalPd).setOfferToken(finalToken).build();
                        var l = ArrayList.$new(); l.add(pdp);
                        var flowParams = BillingFlowParams.newBuilder().setProductDetailsParamsList(l).build();
                        var r = bc.launchBillingFlow(Java.cast(uiAct, Activity), flowParams);
                        S({ ev: "launched", code: r.getResponseCode(), msg: String(r.getDebugMessage() || "") });
                    } catch (e) { S({ ev: "launch_err", m: String(e) }); }
                }
            }
        }).$new(), 1500);
    }

    bc.startConnection(stateListener);
});
setInterval(function () {}, 1000);   // Mantiene el script activo
